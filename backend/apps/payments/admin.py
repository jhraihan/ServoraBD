from django import forms
from django.contrib import admin
from django.shortcuts import get_object_or_404
from unfold.admin import ModelAdmin, TabularInline
from unfold.decorators import action
from unfold.widgets import UnfoldAdminTextareaWidget

from apps.common.admin_actions import ConfirmForm, money_field, perform

from . import services
from .models import LedgerEntry, Payment


class LedgerEntryInline(TabularInline):
    model = LedgerEntry
    extra = 0
    can_delete = False
    readonly_fields = ["kind", "amount", "description", "reference",
                       "recorded_by", "created_at"]
    fields = readonly_fields

    def has_add_permission(self, request, obj=None):
        return False


class PaymentResolutionForm(ConfirmForm):
    settled_amount = money_field("Amount actually paid (BDT)")
    note = forms.CharField(label="How you decided",
                           widget=UnfoldAdminTextareaWidget, max_length=1000)


@admin.register(Payment)
class PaymentAdmin(ModelAdmin):
    list_display = ["id", "booking", "provider", "method", "status",
                    "provider_recorded_amount", "customer_confirmed_amount",
                    "settled_amount", "commission_amount"]
    list_filter = ["status", "method"]
    search_fields = ["provider__display_name", "customer__user__phone",
                     "gateway_reference"]
    readonly_fields = [f.name for f in Payment._meta.fields]
    inlines = [LedgerEntryInline]
    actions_detail = ["resolve"]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @action(description="Resolve flagged payment", url_path="resolve",
            icon="task_alt", permissions=["change"],
            dialog={"title": "Resolve this flagged payment",
                    "description": "The provider and customer reported "
                                   "different amounts. Settle it at the "
                                   "amount that was really paid.",
                    "form_class": PaymentResolutionForm,
                    "form_submit_text": "Settle"})
    def resolve(self, request, form, object_id):
        payment = get_object_or_404(Payment, pk=object_id)
        amount = form.cleaned_data["settled_amount"]
        return perform(
            self, request, payment,
            lambda: services.resolve_flagged_payment(
                payment_id=payment.pk, admin_user_id=request.user.pk,
                settled_amount=amount, note=form.cleaned_data["note"]),
            "Settled at %s BDT." % amount,
        )


@admin.register(LedgerEntry)
class LedgerEntryAdmin(ModelAdmin):
    list_display = ["provider", "kind", "amount", "booking", "created_at"]
    list_filter = ["kind"]
    search_fields = ["provider__display_name", "reference"]
    readonly_fields = [f.name for f in LedgerEntry._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
