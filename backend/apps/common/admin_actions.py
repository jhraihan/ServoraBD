from decimal import Decimal

from django import forms
from django.contrib import messages
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import redirect
from django.urls import reverse
from unfold.forms import BaseDialogForm
from unfold.widgets import (
    UnfoldAdminDecimalFieldWidget, UnfoldAdminTextareaWidget,
    UnfoldAdminTextInputWidget,
)

from .exceptions import DomainError


class ConfirmForm(BaseDialogForm):
    pass


class ReasonForm(BaseDialogForm):
    reason = forms.CharField(widget=UnfoldAdminTextareaWidget, max_length=1000)

    def clean_reason(self):
        reason = self.cleaned_data["reason"].strip()
        if not reason:
            raise forms.ValidationError("Give a reason.")
        return reason


def money_field(label, required=True):
    return forms.DecimalField(label=label, required=required,
                              max_digits=10, decimal_places=2,
                              min_value=Decimal("0"),
                              widget=UnfoldAdminDecimalFieldWidget)


def text_field(label, required=False):
    return forms.CharField(label=label, required=required, max_length=200,
                           widget=UnfoldAdminTextInputWidget)


def change_url(obj):
    meta = obj._meta
    return reverse("admin:%s_%s_change" % (meta.app_label, meta.model_name),
                   args=[obj.pk])


def finish(request, url):
    if request.headers.get("HX-Request"):
        response = HttpResponse()
        response["HX-Redirect"] = url
        return response
    return redirect(url)


def perform(model_admin, request, obj, operation, success):
    try:
        with transaction.atomic():
            operation()
    except DomainError as exc:
        model_admin.message_user(request, exc.message, messages.ERROR)
    else:
        model_admin.log_change(request, obj, success)
        model_admin.message_user(request, success, messages.SUCCESS)
    return finish(request, change_url(obj))
