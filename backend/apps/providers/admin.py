from django import forms
from django.contrib import admin
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils.html import format_html
from unfold.admin import ModelAdmin
from unfold.decorators import action

from apps.common.admin_actions import ConfirmForm, ReasonForm, perform

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
class ProviderServiceAdmin(ModelAdmin):
    list_display = ["provider", "service", "price", "is_active"]
    list_filter = ["is_active", "service__category"]
    search_fields = ["provider__display_name", "service__name"]
    autocomplete_fields = ["service"]

@admin.register(ServiceArea)
class ServiceAreaAdmin(ModelAdmin):
    list_display = ["provider", "location", "travel_surcharge"]
    search_fields = ["provider__display_name", "location__name"]
    autocomplete_fields = ["location"]

@admin.register(Availability)
class AvailabilityAdmin(ModelAdmin):
    list_display = ["provider", "weekday", "start_time", "end_time"]
    list_filter = ["weekday"]
    search_fields = ["provider__display_name"]

@admin.register(AvailabilityException)
class AvailabilityExceptionAdmin(ModelAdmin):
    list_display = ["provider", "date", "is_available", "reason"]
    list_filter = ["is_available"]
    search_fields = ["provider__display_name"]

@admin.register(VerificationDocument)
class VerificationDocumentAdmin(ModelAdmin):
    list_display = ["provider", "document_type", "status", "created_at",
                    "reviewed_at"]
    list_filter = ["status", "document_type"]
    search_fields = ["provider__display_name"]
    form = VerificationDecisionForm
    exclude = ["file"]
    actions_detail = ["approve", "reject"]

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

    @action(description="Approve", url_path="approve", icon="check_circle",
            permissions=["change"],
            dialog={"title": "Approve this document",
                    "description": "Marks the provider verified for this "
                                   "document type and updates their trust "
                                   "score.",
                    "form_class": ConfirmForm,
                    "form_submit_text": "Approve"})
    def approve(self, request, form, object_id):
        document = get_object_or_404(VerificationDocument, pk=object_id)
        return perform(
            self, request, document,
            lambda: services.decide_verification(
                document_id=document.pk, reviewer_id=request.user.pk,
                approve=True),
            "Approved.",
        )

    @action(description="Reject", url_path="reject", icon="cancel",
            permissions=["change"],
            dialog={"title": "Reject this document",
                    "description": "The provider sees your reason and can "
                                   "upload a new document.",
                    "form_class": ReasonForm,
                    "form_submit_text": "Reject"})
    def reject(self, request, form, object_id):
        document = get_object_or_404(VerificationDocument, pk=object_id)
        reason = form.cleaned_data["reason"]
        return perform(
            self, request, document,
            lambda: services.decide_verification(
                document_id=document.pk, reviewer_id=request.user.pk,
                approve=False, rejection_reason=reason),
            "Rejected: %s" % reason,
        )

@admin.register(WorkPhoto)
class WorkPhotoAdmin(ModelAdmin):
    list_display = ["provider", "caption", "display_order"]
    search_fields = ["provider__display_name"]
