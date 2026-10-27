from django import forms
from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from . import services
from .models import (
    Availability, AvailabilityException, ProviderService, ServiceArea,
    VerificationDocument, WorkPhoto,
)

class VerificationDecisionForm(forms.ModelForm):
    def clean(self):
        cleaned = super().clean()
        if cleaned.get("status") == VerificationDocument.Status.REJECTED and \
                not cleaned.get("rejection_reason", "").strip():
            self.add_error("rejection_reason",
                           "Give a reason for rejecting this document.")
        return cleaned

@admin.register(ProviderService)
class ProviderServiceAdmin(admin.ModelAdmin):
    list_display = ["provider", "service", "price", "is_active"]
    list_filter = ["is_active", "service__category"]
    search_fields = ["provider__display_name", "service__name"]
    autocomplete_fields = ["service"]

@admin.register(ServiceArea)
class ServiceAreaAdmin(admin.ModelAdmin):
    list_display = ["provider", "location", "travel_surcharge"]
    search_fields = ["provider__display_name", "location__name"]
    autocomplete_fields = ["location"]

@admin.register(Availability)
class AvailabilityAdmin(admin.ModelAdmin):
    list_display = ["provider", "weekday", "start_time", "end_time"]
    list_filter = ["weekday"]
    search_fields = ["provider__display_name"]

@admin.register(AvailabilityException)
class AvailabilityExceptionAdmin(admin.ModelAdmin):
    list_display = ["provider", "date", "is_available", "reason"]
    list_filter = ["is_available"]
    search_fields = ["provider__display_name"]

@admin.register(VerificationDocument)
class VerificationDocumentAdmin(admin.ModelAdmin):
    list_display = ["provider", "document_type", "status", "created_at",
                    "reviewed_at"]
    list_filter = ["status", "document_type"]
    search_fields = ["provider__display_name"]
    form = VerificationDecisionForm
    exclude = ["file"]

    def get_readonly_fields(self, request, obj=None):
        fields = ["document", "provider", "document_type", "created_at",
                  "reviewed_at", "reviewed_by", "purge_after"]
        if obj is not None and obj.is_reviewed:
            fields += ["status", "rejection_reason"]
        return fields

    def has_add_permission(self, request):
        return False

    def save_model(self, request, obj, form, change):
        if "status" not in form.changed_data or \
                obj.status == VerificationDocument.Status.PENDING:
            return
        services.decide_verification(
            document_id=obj.pk,
            reviewer_id=request.user.id,
            approve=obj.status == VerificationDocument.Status.APPROVED,
            rejection_reason=obj.rejection_reason,
        )

    @admin.display(description="Document")
    def document(self, obj):
        if not obj.file:
            return "No file (purged or never uploaded)"
        return format_html(
            '<a href="{}" target="_blank" rel="noopener">{}</a>',
            reverse("providers:verification-file", args=[obj.pk]),
            obj.file_basename,
        )

@admin.register(WorkPhoto)
class WorkPhotoAdmin(admin.ModelAdmin):
    list_display = ["provider", "caption", "display_order"]
    search_fields = ["provider__display_name"]
