import pytest
from django.contrib import admin
from django.contrib.admin.models import LogEntry
from django.contrib.auth.models import Permission
from django.test import RequestFactory
from django.urls import reverse
from django_otp.plugins.otp_totp.models import TOTPDevice
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts import services
from apps.accounts.models import User
from apps.common.exceptions import DomainError
from apps.common.testing import (
    admin_session, assert_change_page_and_dialogs_render, post_action,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def superuser():
    return User.objects.create_superuser(phone="+8801612345678",
                                         password="adminpass123")


@pytest.fixture
def customer():
    return services.register_user(phone="+8801712345678",
                                  password="testpass123")


def test_suspend_action_signs_the_user_out_everywhere(superuser, customer):
    RefreshToken.for_user(customer)
    client = admin_session(superuser)
    assert_change_page_and_dialogs_render(
        client, customer, ["suspend", "unsuspend", "reset_two_factor"])

    resp = post_action(client, "accounts_user_suspend", customer,
                       reason="Abusive messages to providers")

    assert resp.status_code == 200
    assert resp["HX-Redirect"] == reverse("admin:accounts_user_change",
                                          args=[customer.pk])
    customer.refresh_from_db()
    assert customer.is_suspended
    assert customer.suspension_reason == "Abusive messages to providers"
    assert BlacklistedToken.objects.filter(
        token__user=customer).count() == 1
    assert LogEntry.objects.filter(
        object_id=str(customer.pk),
        change_message__contains="Abusive").exists()


def test_suspend_needs_a_reason(superuser, customer):
    resp = post_action(admin_session(superuser), "accounts_user_suspend",
                       customer, reason="   ")

    assert resp.status_code == 200
    assert "HX-Redirect" not in resp
    customer.refresh_from_db()
    assert not customer.is_suspended


def test_opening_an_action_changes_nothing(superuser, customer):
    resp = admin_session(superuser).get(
        reverse("admin:accounts_user_suspend", args=[customer.pk]))

    assert resp.status_code == 200
    customer.refresh_from_db()
    assert not customer.is_suspended


def test_reinstate_action(superuser, customer):
    services.suspend_user(user_id=customer.pk, admin_user_id=superuser.pk,
                          reason="Spam")

    post_action(admin_session(superuser), "accounts_user_unsuspend",
                customer)

    customer.refresh_from_db()
    assert not customer.is_suspended
    assert customer.suspension_reason == ""


def test_staff_cannot_suspend_a_superuser(superuser):
    staff = User.objects.create_user(phone="+8801812345678",
                                     password="staffpass123", is_staff=True)
    staff.user_permissions.add(*Permission.objects.filter(
        codename__in=["view_user", "change_user"]))

    post_action(admin_session(staff), "accounts_user_suspend", superuser,
                reason="Takeover attempt")

    superuser.refresh_from_db()
    assert not superuser.is_suspended


def test_staff_without_permission_cannot_suspend(customer):
    staff = User.objects.create_user(phone="+8801812345678",
                                     password="staffpass123", is_staff=True)
    staff.user_permissions.add(Permission.objects.get(codename="view_user"))

    resp = post_action(admin_session(staff), "accounts_user_suspend",
                       customer, reason="No authority")

    assert resp.status_code == 403
    customer.refresh_from_db()
    assert not customer.is_suspended


def test_reset_two_factor_action_removes_the_app(superuser):
    staff = User.objects.create_user(phone="+8801812345678",
                                     password="staffpass123", is_staff=True)
    TOTPDevice.objects.create(user=staff, name="Lost phone", confirmed=True)

    post_action(admin_session(superuser), "accounts_user_reset_two_factor",
                staff)

    assert not TOTPDevice.objects.filter(user=staff).exists()


def test_nobody_can_suspend_themselves(superuser):
    with pytest.raises(DomainError):
        services.suspend_user(user_id=superuser.pk,
                              admin_user_id=superuser.pk, reason="Oops")


def test_suspension_fields_are_only_set_through_the_action(superuser):
    request = RequestFactory().get("/admin/")
    request.user = superuser

    readonly = admin.site._registry[User].get_readonly_fields(request)
    assert {"suspended_at", "suspension_reason"} <= set(readonly)
