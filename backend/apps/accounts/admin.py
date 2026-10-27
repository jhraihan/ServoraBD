from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.db import transaction
from django.shortcuts import get_object_or_404
from django_otp.plugins.otp_totp.models import TOTPDevice
from unfold.admin import ModelAdmin
from unfold.decorators import action, display
from unfold.forms import (
    AdminPasswordChangeForm, UserChangeForm, UserCreationForm,
)

from apps.common.admin_actions import (
    ConfirmForm, ReasonForm, money_field, perform, text_field,
)
from apps.common.exceptions import DomainError
from apps.payments import services as payment_services
from apps.trust import engine

from . import services
from .models import CustomerProfile, PhoneOTP, ProviderProfile, User

class SuspendedFilter(admin.SimpleListFilter):
    title = "suspended"
    parameter_name = "suspended"

    def lookups(self, request, model_admin):
        return [("yes", "Suspended"), ("no", "Not suspended")]

    def queryset(self, request, queryset):
        if self.value() == "yes":
            return queryset.filter(suspended_at__isnull=False)
        if self.value() == "no":
            return queryset.filter(suspended_at__isnull=True)
        return queryset

@admin.register(User)
class UserAdmin(BaseUserAdmin, ModelAdmin):
    form = UserChangeForm
    add_form = UserCreationForm
    change_password_form = AdminPasswordChangeForm

    ordering = ["-date_joined"]
    list_display = ["__str__", "phone", "email", "active_role",
                    "phone_verified", "is_active", "is_staff", "suspended"]
    list_filter = ["active_role", "phone_verified", "is_active", "is_staff",
                   SuspendedFilter]
    search_fields = ["phone", "email", "full_name"]
    actions_detail = ["suspend", "unsuspend", "reset_two_factor"]

    fieldsets = (
        (None, {"fields": ("phone", "email", "password")}),
        ("Personal", {"fields": ("full_name",)}),
        ("Verification", {"fields": ("phone_verified", "email_verified")}),
        ("Roles", {"fields": ("active_role",)}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser",
                                    "groups", "user_permissions")}),
        ("Suspension", {"fields": ("suspended_at", "suspension_reason")}),
        ("Dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("phone", "email", "full_name", "password1",
                       "password2"),
        }),
    )

    @display(description="Suspended", boolean=True)
    def suspended(self, obj):
        return obj.is_suspended

    def get_readonly_fields(self, request, obj=None):
        fields = list(super().get_readonly_fields(request, obj))
        fields += ["suspended_at", "suspension_reason"]
        if not request.user.is_superuser:
            fields += ["is_staff", "is_superuser", "groups",
                       "user_permissions"]
        return fields

    def has_change_permission(self, request, obj=None):
        if obj is not None and obj.is_superuser and \
                not request.user.is_superuser:
            return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        if obj is not None and obj.is_superuser and \
                not request.user.is_superuser:
            return False
        return super().has_delete_permission(request, obj)

    def has_suspend_permission(self, request, object_id=None):
        return request.user.has_perm("accounts.change_user")

    def has_reset_two_factor_permission(self, request, object_id=None):
        return request.user.has_perm("otp_totp.delete_totpdevice")

    def _target(self, request, object_id):
        user = get_object_or_404(User, pk=object_id)
        if user.is_superuser and not request.user.is_superuser:
            raise DomainError("Only a superuser can act on a superuser.",
                              code="superuser_protected")
        return user

    @action(description="Suspend", url_path="suspend", icon="block",
            permissions=["suspend"],
            dialog={"title": "Suspend this account",
                    "description": "They are signed out of the app and the "
                                   "admin, and cannot sign in until "
                                   "reinstated.",
                    "form_class": ReasonForm,
                    "form_submit_text": "Suspend"})
    def suspend(self, request, form, object_id):
        user = get_object_or_404(User, pk=object_id)
        reason = form.cleaned_data["reason"]

        def operation():
            self._target(request, object_id)
            services.suspend_user(user_id=user.pk,
                                  admin_user_id=request.user.pk,
                                  reason=reason)

        return perform(self, request, user, operation,
                       "Suspended: %s" % reason)

    @action(description="Reinstate", url_path="unsuspend",
            icon="lock_open", permissions=["suspend"],
            dialog={"title": "Reinstate this account",
                    "description": "They can sign in again. Sessions ended "
                                   "by the suspension stay ended.",
                    "form_class": ConfirmForm,
                    "form_submit_text": "Reinstate"})
    def unsuspend(self, request, form, object_id):
        user = get_object_or_404(User, pk=object_id)

        def operation():
            self._target(request, object_id)
            services.unsuspend_user(user_id=user.pk,
                                    admin_user_id=request.user.pk)

        return perform(self, request, user, operation, "Reinstated.")

    @action(description="Reset two-factor", url_path="reset-two-factor",
            icon="phonelink_erase",
            permissions=["reset_two_factor"],
            dialog={"title": "Reset two-factor sign-in",
                    "description": "Use this when a staff member loses "
                                   "their phone. They set up a new app at "
                                   "their next admin login.",
                    "form_class": ConfirmForm,
                    "form_submit_text": "Reset"})
    def reset_two_factor(self, request, form, object_id):
        user = get_object_or_404(User, pk=object_id)

        def operation():
            self._target(request, object_id)
            TOTPDevice.objects.filter(user=user).delete()

        return perform(self, request, user, operation,
                       "Two-factor sign-in reset.")

@admin.register(CustomerProfile)
class CustomerProfileAdmin(ModelAdmin):
    list_display = ["__str__", "created_at"]
    search_fields = ["user__phone", "user__email", "user__full_name"]

class SettlementForm(ConfirmForm):
    amount = money_field("Amount received")
    reference = text_field("Reference, e.g. bKash transaction ID")

@admin.register(ProviderProfile)
class ProviderProfileAdmin(ModelAdmin):
    list_display = ["display_name", "trust_score", "trust_tier",
                    "jobs_completed", "identity_verified",
                    "is_accepting_work"]
    list_filter = ["trust_tier", "identity_verified", "is_accepting_work"]
    search_fields = ["display_name", "user__phone", "user__email"]
    actions_detail = ["recompute_trust", "record_settlement"]

    readonly_fields = ["trust_score", "trust_tier", "trust_computed_at",
                       "jobs_completed", "jobs_cancelled", "jobs_accepted",
                       "requests_received", "median_response_seconds",
                       "outstanding_payable"]

    @display(description="Owes the platform (BDT)")
    def outstanding_payable(self, obj):
        return payment_services.outstanding_payable(obj.pk)

    def has_record_settlement_permission(self, request, object_id=None):
        return request.user.has_perm("payments.add_ledgerentry")

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if change and form.changed_data:
            transaction.on_commit(lambda: engine.recompute(obj.pk))

    @action(description="Recompute trust", url_path="recompute-trust",
            icon="refresh",
            permissions=["change"],
            dialog={"title": "Recompute trust score",
                    "description": "Recalculates the score from current "
                                   "data and records a snapshot.",
                    "form_class": ConfirmForm,
                    "form_submit_text": "Recompute"})
    def recompute_trust(self, request, form, object_id):
        provider = get_object_or_404(ProviderProfile, pk=object_id)
        return perform(self, request, provider,
                       lambda: engine.recompute(provider.pk),
                       "Trust score recomputed.")

    @action(description="Record settlement", url_path="record-settlement",
            icon="payments", permissions=["record_settlement"],
            dialog={"title": "Record a commission settlement",
                    "description": "Cash the provider paid the platform. "
                                   "It cannot exceed what they owe.",
                    "form_class": SettlementForm,
                    "form_submit_text": "Record"})
    def record_settlement(self, request, form, object_id):
        provider = get_object_or_404(ProviderProfile, pk=object_id)
        amount = form.cleaned_data["amount"]
        return perform(
            self, request, provider,
            lambda: payment_services.record_provider_settlement(
                provider_id=provider.pk, amount=amount,
                admin_user_id=request.user.pk,
                reference=form.cleaned_data["reference"]),
            "Settlement of %s BDT recorded." % amount,
        )

@admin.register(PhoneOTP)
class PhoneOTPAdmin(ModelAdmin):
    list_display = ["phone", "purpose", "created_at", "expires_at",
                    "consumed_at", "attempts"]
    list_filter = ["purpose"]
    search_fields = ["phone"]
    readonly_fields = ["code_hash", "created_at", "updated_at"]
