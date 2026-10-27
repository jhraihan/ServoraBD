from django import forms
from django.contrib import admin
from django.shortcuts import get_object_or_404
from unfold.admin import ModelAdmin, TabularInline
from unfold.decorators import action
from unfold.widgets import UnfoldAdminTextareaWidget

from apps.common.admin_actions import ConfirmForm, money_field, perform

from . import services
from .models import (
    Booking, BookingEvent, ProviderResponse, RequestPhoto, ServiceRequest,
)

class BookingEventInline(TabularInline):
    model = BookingEvent
    extra = 0
    readonly_fields = ["from_state", "to_state", "actor", "actor_user",
                       "reason", "metadata", "created_at"]
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False

@admin.register(ServiceRequest)
class ServiceRequestAdmin(ModelAdmin):
    list_display = ["id", "customer", "service", "location", "state",
                    "expires_at", "created_at"]
    list_filter = ["state", "kind"]
    search_fields = ["customer__user__phone", "service__name"]
    readonly_fields = [f.name for f in ServiceRequest._meta.fields]

    def has_add_permission(self, request):
        return False

class DisputeResolutionForm(ConfirmForm):
    settled_price = money_field("Price the customer pays (BDT)",
                                required=False)
    note = forms.CharField(label="Decision and reasoning",
                           widget=UnfoldAdminTextareaWidget, max_length=1000)

@admin.register(Booking)
class BookingAdmin(ModelAdmin):
    list_display = ["id", "provider", "customer", "state", "scheduled_for",
                    "agreed_price", "final_price"]
    list_filter = ["state"]
    search_fields = ["provider__display_name", "customer__user__phone"]
    readonly_fields = [f.name for f in Booking._meta.fields]
    inlines = [BookingEventInline]
    actions_detail = ["resolve_dispute"]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @action(description="Resolve dispute", url_path="resolve-dispute",
            icon="gavel", permissions=["change"],
            dialog={"title": "Resolve this dispute",
                    "description": "Closes the booking as completed. If it "
                                   "was never confirmed, the price you set "
                                   "is what gets paid. If it was, the "
                                   "payment already recorded stands.",
                    "form_class": DisputeResolutionForm,
                    "form_submit_text": "Resolve"})
    def resolve_dispute(self, request, form, object_id):
        booking = get_object_or_404(Booking, pk=object_id)
        note = form.cleaned_data["note"]
        return perform(
            self, request, booking,
            lambda: services.resolve_dispute(
                booking_id=booking.pk, admin_user_id=request.user.pk,
                note=note,
                settled_price=form.cleaned_data["settled_price"]),
            "Dispute resolved: %s" % note,
        )

@admin.register(ProviderResponse)
class ProviderResponseAdmin(ModelAdmin):
    list_display = ["request", "provider", "decision", "response_seconds",
                    "created_at"]
    list_filter = ["decision"]
    readonly_fields = [f.name for f in ProviderResponse._meta.fields]

    def has_add_permission(self, request):
        return False

@admin.register(BookingEvent)
class BookingEventAdmin(ModelAdmin):
    list_display = ["booking", "from_state", "to_state", "actor",
                    "created_at"]
    list_filter = ["actor", "to_state"]
    readonly_fields = [f.name for f in BookingEvent._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

@admin.register(RequestPhoto)
class RequestPhotoAdmin(ModelAdmin):
    list_display = ["request", "created_at"]
