import logging
from decimal import Decimal

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from apps.accounts.models import CustomerProfile, ProviderProfile
from apps.catalogue.models import Location, Service
from apps.common.exceptions import DomainError, NotFound
from apps.providers.models import ProviderService, ServiceArea

from .models import (
    AUTO_CONFIRM_HOURS, Booking, BookingEvent, ProviderResponse,
    ServiceRequest,
)
from .state_machine import assert_can_transition

logger = logging.getLogger(__name__)

State = Booking.State


def _record_event(booking, *, from_state, to_state, actor, actor_user_id=None,
                  reason="", metadata=None):
    return BookingEvent.objects.create(
        booking=booking,
        from_state=from_state or "",
        to_state=to_state,
        actor=actor,
        actor_user_id=actor_user_id,
        reason=reason,
        metadata=metadata or {},
    )


@transaction.atomic
def create_request(*, customer_id, service_id, location_id, address,
                   description, preferred_start, preferred_end,
                   target_provider_id=None):
    customer = CustomerProfile.objects.filter(pk=customer_id).first()
    if customer is None:
        raise NotFound("No such customer.", code="customer_not_found")

    service = Service.objects.filter(pk=service_id, is_active=True).first()
    if service is None:
        raise NotFound("No such service.", code="service_not_found")

    location = Location.objects.filter(pk=location_id, is_active=True).first()
    if location is None:
        raise NotFound("No such location.", code="location_not_found")

    if preferred_end <= preferred_start:
        raise DomainError("The time window must end after it starts.",
                          code="invalid_window")

    if preferred_start <= timezone.now():
        raise DomainError("The preferred time must be in the future.",
                          code="window_in_past")

    kind = ServiceRequest.Kind.BROADCAST
    target = None
    if target_provider_id is not None:
        target = ProviderProfile.objects.filter(
            pk=target_provider_id, is_accepting_work=True,
        ).first()
        if target is None:
            raise NotFound("That provider is not available.",
                           code="provider_not_found")
        kind = ServiceRequest.Kind.DIRECT

    request = ServiceRequest.objects.create(
        customer=customer,
        service=service,
        location=location,
        address=address,
        description=description,
        kind=kind,
        target_provider=target,
        preferred_start=preferred_start,
        preferred_end=preferred_end,
        expires_at=ServiceRequest.default_expiry(),
    )

    _bump_requests_received(request)
    logger.info("Request %s created by customer %s", request.id, customer_id)
    return request


def _bump_requests_received(request):
    provider_ids = list(
        matching_provider_ids(request).values_list("pk", flat=True)
    )
    if provider_ids:
        ProviderProfile.objects.filter(pk__in=provider_ids).update(
            requests_received=F("requests_received") + 1,
        )


def matching_provider_ids(request):
    if request.kind == ServiceRequest.Kind.DIRECT:
        return ProviderProfile.objects.filter(pk=request.target_provider_id)

    area_ids = request.location.descendant_ids() + [
        node.pk for node in request.location.ancestors()
        if node.level != Location.Level.CITY
    ]

    return ProviderProfile.objects.filter(
        pk__in=ServiceArea.objects.filter(
            location_id__in=area_ids
        ).values("provider_id"),
        is_accepting_work=True,
        user__is_active=True,
        user__suspended_at__isnull=True,
    ).filter(
        pk__in=ProviderService.objects.filter(
            service_id=request.service_id, is_active=True,
        ).values("provider_id")
    ).exclude(trust_tier=ProviderProfile.Tier.UNDER_REVIEW)


def can_provider_respond(request, provider_id):
    return matching_provider_ids(request).filter(pk=provider_id).exists()


@transaction.atomic
def withdraw_request(*, request_id, customer_id, reason=""):
    request = (
        ServiceRequest.objects
        .select_for_update()
        .filter(pk=request_id, customer_id=customer_id)
        .first()
    )
    if request is None:
        raise NotFound("No such request.", code="request_not_found")

    if not request.is_open:
        raise DomainError(
            "Only an open request can be withdrawn.",
            code="request_not_open",
            details={"state": request.state},
        )

    request.state = ServiceRequest.State.WITHDRAWN
    request.closed_at = timezone.now()
    request.save(update_fields=["state", "closed_at", "updated_at"])
    return request


@transaction.atomic
def respond_to_request(*, request_id, provider_id, accept, reason="",
                       scheduled_for=None, price=None):
    request = (
        ServiceRequest.objects
        .select_for_update()
        .select_related("service", "location", "customer")
        .filter(pk=request_id)
        .first()
    )
    if request is None:
        raise NotFound("No such request.", code="request_not_found")

    provider = ProviderProfile.objects.filter(pk=provider_id).first()
    if provider is None:
        raise NotFound("No such provider.", code="provider_not_found")

    if not can_provider_respond(request, provider_id):
        raise DomainError(
            "This request is not open to you.",
            code="not_eligible",
        )

    if request.is_expired and request.is_open:
        _expire_request(request)

    if not request.is_open:
        raise DomainError(
            "This request is no longer open.",
            code="request_closed",
            details={"state": request.state},
        )

    if ProviderResponse.objects.filter(request=request,
                                       provider=provider).exists():
        raise DomainError("You have already responded to this request.",
                          code="already_responded")

    elapsed = int((timezone.now() - request.created_at).total_seconds())
    decision = (
        ProviderResponse.Decision.ACCEPTED if accept
        else ProviderResponse.Decision.DECLINED
    )
    ProviderResponse.objects.create(
        request=request, provider=provider, decision=decision,
        reason=reason, response_seconds=elapsed,
    )
    refresh_median_response(provider_id)

    if not accept:
        logger.info("Provider %s declined request %s", provider_id, request.id)
        return None

    return _accept_request(request, provider, scheduled_for, price)


def _accept_request(request, provider, scheduled_for, price):
    offering = ProviderService.objects.filter(
        provider=provider, service_id=request.service_id, is_active=True,
    ).first()
    if offering is None:
        raise DomainError("You no longer offer this service.",
                          code="offering_missing")

    agreed_price = price if price is not None else offering.price
    if agreed_price < 0:
        raise DomainError("Price cannot be negative.", code="invalid_price")

    when = scheduled_for or request.preferred_start
    if when < timezone.now():
        raise DomainError("The scheduled time must be in the future.",
                          code="schedule_in_past")

    request.state = ServiceRequest.State.ACCEPTED
    request.closed_at = timezone.now()
    request.save(update_fields=["state", "closed_at", "updated_at"])

    booking = Booking.objects.create(
        request=request,
        provider=provider,
        customer=request.customer,
        scheduled_for=when,
        agreed_price=agreed_price,
    )
    _record_event(
        booking, from_state="", to_state=State.SCHEDULED,
        actor=BookingEvent.Actor.PROVIDER,
        actor_user_id=provider.user_id,
        metadata={"agreed_price": str(agreed_price)},
    )

    ProviderProfile.objects.filter(pk=provider.pk).update(
        jobs_accepted=F("jobs_accepted") + 1,
    )

    logger.info("Booking %s created from request %s", booking.id, request.id)
    return booking


def refresh_median_response(provider_id):
    seconds = list(
        ProviderResponse.objects
        .filter(provider_id=provider_id)
        .order_by("-created_at")
        .values_list("response_seconds", flat=True)[:30]
    )
    if not seconds:
        return

    seconds.sort()
    middle = len(seconds) // 2
    median = (
        seconds[middle] if len(seconds) % 2
        else (seconds[middle - 1] + seconds[middle]) // 2
    )
    ProviderProfile.objects.filter(pk=provider_id).update(
        median_response_seconds=median,
    )


def _transition(booking, *, to_state, actor, actor_user_id=None, reason="",
                metadata=None, updates=None):
    assert_can_transition(booking.state, to_state)

    from_state = booking.state
    booking.state = to_state
    fields = ["state", "updated_at"]

    for name, value in (updates or {}).items():
        setattr(booking, name, value)
        fields.append(name)

    booking.save(update_fields=fields)
    _record_event(booking, from_state=from_state, to_state=to_state,
                  actor=actor, actor_user_id=actor_user_id, reason=reason,
                  metadata=metadata)
    return booking


def _locked_booking(booking_id, **filters):
    booking = (
        Booking.objects
        .select_for_update()
        .select_related("provider", "customer", "request")
        .filter(pk=booking_id, **filters)
        .first()
    )
    if booking is None:
        raise NotFound("No such booking.", code="booking_not_found")
    return booking


@transaction.atomic
def start_job(*, booking_id, provider_id):
    booking = _locked_booking(booking_id, provider_id=provider_id)
    return _transition(
        booking, to_state=State.IN_PROGRESS,
        actor=BookingEvent.Actor.PROVIDER,
        actor_user_id=booking.provider.user_id,
        updates={"started_at": timezone.now()},
    )


@transaction.atomic
def complete_job(*, booking_id, provider_id, final_price=None):
    booking = _locked_booking(booking_id, provider_id=provider_id)

    amount = final_price if final_price is not None else booking.agreed_price
    if amount < 0:
        raise DomainError("Price cannot be negative.", code="invalid_price")

    return _transition(
        booking, to_state=State.AWAITING_CONFIRM,
        actor=BookingEvent.Actor.PROVIDER,
        actor_user_id=booking.provider.user_id,
        metadata={"final_price": str(amount)},
        updates={"completed_at": timezone.now(), "final_price": amount},
    )


@transaction.atomic
def confirm_completion(*, booking_id, customer_id, confirmed_price=None):
    booking = _locked_booking(booking_id, customer_id=customer_id)

    amount = (
        confirmed_price if confirmed_price is not None else booking.final_price
    )
    booking = _transition(
        booking, to_state=State.COMPLETED,
        actor=BookingEvent.Actor.CUSTOMER,
        actor_user_id=booking.customer.user_id,
        metadata={"confirmed_price": str(amount) if amount else None},
        updates={
            "confirmed_at": timezone.now(),
            "customer_confirmed_price": amount,
        },
    )
    _on_completed(booking)
    return booking


def _on_completed(booking):
    from apps.payments.services import record_completion_payment

    ProviderProfile.objects.filter(pk=booking.provider_id).update(
        jobs_completed=F("jobs_completed") + 1,
    )
    record_completion_payment(booking_id=booking.pk)
    _recompute_trust(booking.provider_id, trigger="booking_completed")


@transaction.atomic
def cancel_booking(*, booking_id, actor, actor_user_id, reason,
                   customer_id=None, provider_id=None):
    filters = {}
    if customer_id is not None:
        filters["customer_id"] = customer_id
    if provider_id is not None:
        filters["provider_id"] = provider_id

    booking = _locked_booking(booking_id, **filters)

    if not reason:
        raise DomainError("A cancellation needs a reason.",
                          code="reason_required")

    to_state = (
        State.CANCELLED_CUSTOMER if actor == BookingEvent.Actor.CUSTOMER
        else State.CANCELLED_PROVIDER
    )

    booking = _transition(
        booking, to_state=to_state, actor=actor, actor_user_id=actor_user_id,
        reason=reason,
        updates={
            "cancelled_at": timezone.now(),
            "cancelled_by": actor,
            "cancel_reason": reason,
        },
    )

    if to_state == State.CANCELLED_PROVIDER:
        ProviderProfile.objects.filter(pk=booking.provider_id).update(
            jobs_cancelled=F("jobs_cancelled") + 1,
        )
        _recompute_trust(booking.provider_id, trigger="booking_cancelled")

    return booking


@transaction.atomic
def open_dispute(*, booking_id, customer_id, reason):
    booking = _locked_booking(booking_id, customer_id=customer_id)

    if not reason:
        raise DomainError("A dispute needs a reason.", code="reason_required")

    return _transition(
        booking, to_state=State.DISPUTED,
        actor=BookingEvent.Actor.CUSTOMER,
        actor_user_id=booking.customer.user_id,
        reason=reason,
    )


@transaction.atomic
def resolve_dispute(*, booking_id, admin_user_id, note, settled_price=None):
    from apps.payments.models import Payment
    from apps.payments.services import resolve_flagged_payment

    booking = _locked_booking(booking_id)

    if booking.state != State.DISPUTED:
        raise DomainError("Only a disputed booking can be resolved.",
                          code="booking_not_disputed",
                          details={"state": booking.state})

    note = (note or "").strip()
    if not note:
        raise DomainError("A resolution needs a note.", code="note_required")

    first_completion = booking.confirmed_at is None
    if first_completion and settled_price is None:
        raise DomainError(
            "This booking was never confirmed, so set the price the "
            "customer pays.",
            code="price_required",
        )
    if settled_price is not None and settled_price < 0:
        raise DomainError("Price cannot be negative.", code="invalid_price")

    updates = {}
    if first_completion:
        updates = {"confirmed_at": timezone.now(),
                   "customer_confirmed_price": settled_price}

    booking = _transition(
        booking, to_state=State.COMPLETED,
        actor=BookingEvent.Actor.ADMIN,
        actor_user_id=admin_user_id,
        reason=note,
        metadata=({"settled_price": str(settled_price)}
                  if settled_price is not None else {}),
        updates=updates,
    )

    if first_completion:
        _on_completed(booking)
        flagged = Payment.objects.filter(
            booking=booking, status=Payment.Status.FLAGGED,
        ).first()
        if flagged is not None:
            resolve_flagged_payment(payment_id=flagged.pk,
                                    admin_user_id=admin_user_id,
                                    settled_amount=settled_price, note=note)

    logger.info("Dispute on booking %s resolved by %s", booking.pk,
                admin_user_id)
    return booking


def _recompute_trust(provider_id, trigger):
    from apps.trust import engine
    from apps.trust.models import TrustSnapshot

    mapped = {
        "booking_completed": TrustSnapshot.Trigger.BOOKING_COMPLETED,
        "booking_cancelled": TrustSnapshot.Trigger.BOOKING_CANCELLED,
    }[trigger]

    transaction.on_commit(
        lambda: engine.recompute(provider_id, trigger=mapped)
    )


def expire_stale_requests(*, now=None):
    now = now or timezone.now()
    stale = ServiceRequest.objects.filter(
        state=ServiceRequest.State.OPEN, expires_at__lte=now,
    )

    expired = 0
    for request in stale.iterator():
        with transaction.atomic():
            locked = (
                ServiceRequest.objects
                .select_for_update()
                .filter(pk=request.pk, state=ServiceRequest.State.OPEN)
                .first()
            )
            if locked is None:
                continue
            _expire_request(locked)
            expired += 1
    return expired


def _expire_request(request):
    request.state = ServiceRequest.State.EXPIRED
    request.closed_at = timezone.now()
    request.save(update_fields=["state", "closed_at", "updated_at"])


def auto_confirm_bookings(*, now=None):
    now = now or timezone.now()
    cutoff = now - timezone.timedelta(hours=AUTO_CONFIRM_HOURS)

    pending = Booking.objects.filter(
        state=State.AWAITING_CONFIRM, completed_at__lte=cutoff,
    )

    confirmed = 0
    for booking in pending.iterator():
        with transaction.atomic():
            locked = (
                Booking.objects
                .select_for_update()
                .filter(pk=booking.pk, state=State.AWAITING_CONFIRM)
                .first()
            )
            if locked is None:
                continue

            locked = _transition(
                locked, to_state=State.COMPLETED,
                actor=BookingEvent.Actor.SYSTEM,
                reason="Auto-confirmed after %d hours." % AUTO_CONFIRM_HOURS,
                updates={
                    "confirmed_at": timezone.now(),
                    "auto_confirmed": True,
                    "customer_confirmed_price": min(locked.final_price,
                                                    locked.agreed_price),
                },
            )
            _on_completed(locked)
            confirmed += 1
    return confirmed
