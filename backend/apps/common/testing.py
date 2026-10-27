from django.test import Client
from django.urls import reverse
from django_otp import DEVICE_ID_SESSION_KEY
from django_otp.plugins.otp_totp.models import TOTPDevice
from rest_framework.test import APIClient


def verified_admin_client(user, client=None):
    client = client or APIClient()
    client.force_login(user)
    device = TOTPDevice.objects.create(user=user, name="Test app",
                                       confirmed=True)
    session = client.session
    session[DEVICE_ID_SESSION_KEY] = device.persistent_id
    session.save()
    return client


def admin_session(user):
    return verified_admin_client(user, Client())


def post_action(client, name, obj, **data):
    return client.post(reverse("admin:%s" % name, args=[obj.pk]),
                       {"_form_submitted": "on", **data},
                       HTTP_HX_REQUEST="true")


def assert_change_page_and_dialogs_render(client, obj, actions):
    meta = obj._meta
    prefix = "admin:%s_%s" % (meta.app_label, meta.model_name)
    page = client.get(reverse(prefix + "_change", args=[obj.pk]))
    assert page.status_code == 200
    for name in actions:
        url = reverse("%s_%s" % (prefix, name), args=[obj.pk])
        assert url.encode() in page.content, name
        assert client.get(url, HTTP_HX_REQUEST="true").status_code == 200
