import logging
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from rest_framework_simplejwt.token_blacklist.models import (
    BlacklistedToken, OutstandingToken,
)

from apps.common.exceptions import (
    DomainError, NotFound, RateLimited, VerificationError,
)

from .models import CustomerProfile, PhoneOTP, ProviderProfile
from .validators import normalise_bd_phone

logger = logging.getLogger(__name__)
User = get_user_model()

@transaction.atomic
def register_user(*, phone=None, email=None, password, full_name="",
                  role=User.Role.CUSTOMER):
    if not phone and not email:
        raise DomainError(
            "Provide a phone number or an email address.",
            code="identifier_required",
        )

    phone = normalise_bd_phone(phone) if phone else None
    email = email.lower().strip() if email else None

    if phone and User.objects.filter(phone=phone).exists():
        raise DomainError("That phone number is already registered.",
                          code="phone_taken")
    if email and User.objects.filter(email=email).exists():
        raise DomainError("That email address is already registered.",
                          code="email_taken")

    user = User.objects.create_user(
        phone=phone, email=email, password=password, full_name=full_name,
        active_role=role,
    )
    create_profile(user_id=user.id, role=role)
    logger.info("Registered user %s as %s", user.id, role)
    return user

@transaction.atomic
def create_profile(*, user_id, role):
    user = User.objects.select_for_update().get(pk=user_id)

    if role == User.Role.CUSTOMER:
        profile, _created = CustomerProfile.objects.get_or_create(user=user)
        return profile

    if role == User.Role.PROVIDER:
        profile, _created = ProviderProfile.objects.get_or_create(
            user=user,
            defaults={"display_name": user.full_name or "New provider"},
        )
        return profile

    raise DomainError("Unknown role.", code="unknown_role")

@transaction.atomic
def switch_active_role(*, user_id, role):
    user = User.objects.select_for_update().get(pk=user_id)

    if role not in user.roles:
        raise DomainError(
            "You do not have a %s profile." % role,
            code="role_not_held",
        )

    user.active_role = role
    user.save(update_fields=["active_role", "updated_at"]
              if hasattr(user, "updated_at") else ["active_role"])
    return user

@transaction.atomic
def suspend_user(*, user_id, admin_user_id, reason):
    reason = (reason or "").strip()
    if not reason:
        raise DomainError("A suspension needs a reason.",
                          code="reason_required")
    if user_id == admin_user_id:
        raise DomainError("You cannot suspend your own account.",
                          code="self_suspension")

    user = User.objects.select_for_update().filter(pk=user_id).first()
    if user is None:
        raise NotFound("No such user.", code="user_not_found")

    user.suspended_at = timezone.now()
    user.suspension_reason = reason
    user.save(update_fields=["suspended_at", "suspension_reason"])
    revoked = revoke_refresh_tokens(user_id=user.pk)
    logger.info("User %s suspended by %s; %d refresh token(s) revoked",
                user.pk, admin_user_id, revoked)
    return user

@transaction.atomic
def unsuspend_user(*, user_id, admin_user_id):
    user = User.objects.select_for_update().filter(pk=user_id).first()
    if user is None:
        raise NotFound("No such user.", code="user_not_found")

    user.suspended_at = None
    user.suspension_reason = ""
    user.save(update_fields=["suspended_at", "suspension_reason"])
    logger.info("User %s reinstated by %s", user.pk, admin_user_id)
    return user

def revoke_refresh_tokens(*, user_id):
    live = OutstandingToken.objects.filter(
        user_id=user_id, expires_at__gt=timezone.now(),
        blacklistedtoken__isnull=True,
    )
    revoked = BlacklistedToken.objects.bulk_create(
        [BlacklistedToken(token=token) for token in live],
        ignore_conflicts=True,
    )
    return len(revoked)

def _recent_send_count(phone, within=timedelta(hours=1)):
    return PhoneOTP.objects.filter(
        phone=phone, created_at__gte=timezone.now() - within
    ).count()

@transaction.atomic
def send_phone_otp(*, phone, purpose=PhoneOTP.Purpose.REGISTRATION):
    phone = normalise_bd_phone(phone)

    if _recent_send_count(phone) >= settings.OTP_MAX_SENDS_PER_HOUR:
        raise RateLimited(
            "Too many verification codes requested. Try again in an hour.",
            details={"phone": phone},
        )

    PhoneOTP.objects.filter(
        phone=phone, purpose=purpose, consumed_at__isnull=True
    ).update(consumed_at=timezone.now())

    code = PhoneOTP.generate_code()
    otp = PhoneOTP.objects.create(
        phone=phone,
        code_hash=PhoneOTP.hash_code(phone, code),
        purpose=purpose,
        expires_at=PhoneOTP.default_expiry(),
    )

    _deliver_otp(phone, code)
    return otp

def _deliver_otp(phone, code):
    if getattr(settings, "OTP_ECHO_TO_LOG", False):
        logger.info("OTP for %s is %s", phone, code)
    else:
        logger.info("OTP issued for %s (delivery pending SMS provider)", phone)

def verify_phone_otp(*, phone, code, purpose=PhoneOTP.Purpose.REGISTRATION):
    phone = normalise_bd_phone(phone)

    with transaction.atomic():
        otp = (
            PhoneOTP.objects
            .select_for_update()
            .filter(phone=phone, purpose=purpose, consumed_at__isnull=True)
            .order_by("-created_at")
            .first()
        )

        if otp is None:
            raise VerificationError(
                "No verification code was requested for that number.",
                code="otp_not_found",
            )

        if otp.is_expired:
            raise VerificationError(
                "That code has expired. Request a new one.",
                code="otp_expired",
            )

        if otp.attempts >= settings.OTP_MAX_VERIFY_ATTEMPTS:
            raise RateLimited(
                "Too many incorrect attempts. Request a new code.",
                details={"phone": phone},
            )

        matched = otp.matches(code)
        if not matched:
            otp.attempts += 1
            otp.save(update_fields=["attempts"])
            remaining = settings.OTP_MAX_VERIFY_ATTEMPTS - otp.attempts

    if not matched:
        raise VerificationError(
            "That code is not correct.",
            code="otp_mismatch",
            details={"attempts_remaining": max(remaining, 0)},
        )

    with transaction.atomic():
        otp.consumed_at = timezone.now()
        otp.save(update_fields=["consumed_at"])

        user = User.objects.select_for_update().filter(phone=phone).first()
        if user and not user.phone_verified:
            user.phone_verified = True
            user.save(update_fields=["phone_verified"])
            logger.info("Phone verified for user %s", user.id)

    return user

def purge_expired_otps(*, older_than_hours=24):
    cutoff = timezone.now() - timedelta(hours=older_than_hours)
    deleted, _ = PhoneOTP.objects.filter(created_at__lt=cutoff).delete()
    return deleted
