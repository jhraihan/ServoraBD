from base64 import b32encode, b64encode
from io import BytesIO

from django import forms
from django.contrib.auth import logout as auth_logout
from django.http import HttpResponse
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.http import url_has_allowed_host_and_scheme, urlencode
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django_otp import login as otp_login
from django_otp.plugins.otp_totp.models import TOTPDevice
from django_otp.qr import write_qrcode_image
from unfold.sites import UnfoldAdminSite

from .throttling import AdminLoginThrottle


def is_verified(user):
    return bool(getattr(user, "is_verified", lambda: False)())


def qr_data_uri(data):
    buffer = BytesIO()
    write_qrcode_image(data, buffer)
    return "data:image/svg+xml;base64,%s" % b64encode(buffer.getvalue()).decode()


class TokenForm(forms.Form):
    token = forms.RegexField(
        label="6-digit code", regex=r"^\d{6}$",
        error_messages={"invalid": "Enter the 6 digits shown in your app."},
        widget=forms.TextInput(attrs={"autocomplete": "one-time-code",
                                      "inputmode": "numeric",
                                      "autofocus": True}),
    )


class ServoraAdminSite(UnfoldAdminSite):
    def has_permission(self, request):
        return (super().has_permission(request)
                and not request.user.is_suspended
                and is_verified(request.user))

    def awaiting_second_factor(self, request):
        user = request.user
        return (user.is_active and user.is_staff
                and not user.is_suspended and not is_verified(user))

    def get_urls(self):
        return [
            path("two-factor/", never_cache(csrf_protect(self.two_factor)),
                 name="two_factor"),
        ] + super().get_urls()

    def login(self, request, extra_context=None):
        if request.method == "POST" and \
                not AdminLoginThrottle().allow_request(request, None):
            return HttpResponse(
                "Too many login attempts. Try again in 15 minutes.",
                status=429, content_type="text/plain",
            )
        if request.method == "GET" and self.awaiting_second_factor(request):
            return redirect(self._two_factor_url(request))

        response = super().login(request, extra_context)
        if request.method == "POST" and self.awaiting_second_factor(request):
            return redirect(self._two_factor_url(request))
        return response

    def two_factor(self, request):
        if request.method == "POST" and "cancel" in request.POST:
            auth_logout(request)
            return redirect("admin:login")

        if not self.awaiting_second_factor(request):
            return redirect("admin:index" if self.has_permission(request)
                            else "admin:login")

        device = TOTPDevice.objects.filter(user=request.user,
                                           confirmed=True).first()
        enrolling = device is None
        if enrolling:
            device = (
                TOTPDevice.objects.filter(user=request.user,
                                          confirmed=False).first()
                or TOTPDevice.objects.create(user=request.user,
                                             name="Authenticator app",
                                             confirmed=False)
            )

        form = TokenForm(request.POST or None)
        if form.is_valid():
            if device.verify_token(form.cleaned_data["token"]):
                if enrolling:
                    device.confirmed = True
                    device.save(update_fields=["confirmed"])
                otp_login(request, device)
                return redirect(self._safe_next(request)
                                or reverse("admin:index",
                                           current_app=self.name))
            form.add_error("token", "That code is not right. Wait for a new "
                                    "one and try again.")

        context = {
            **self.each_context(request),
            "title": ("Set up two-factor sign-in" if enrolling
                      else "Two-factor sign-in"),
            "form": form,
            "enrolling": enrolling,
            "next": self._safe_next(request) or "",
        }
        if enrolling:
            context["qr_code"] = qr_data_uri(device.config_url)
            context["secret"] = b32encode(device.bin_key).decode()
        request.current_app = self.name
        return TemplateResponse(request, "admin/two_factor.html", context)

    def _safe_next(self, request):
        target = request.POST.get("next") or request.GET.get("next")
        if target and url_has_allowed_host_and_scheme(
                target, allowed_hosts={request.get_host()},
                require_https=request.is_secure()):
            return target
        return None

    def _two_factor_url(self, request):
        url = reverse("admin:two_factor", current_app=self.name)
        target = self._safe_next(request)
        return "%s?%s" % (url, urlencode({"next": target})) if target else url
