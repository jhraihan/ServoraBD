import pytest
from django.contrib import admin
from django.contrib.auth.models import Permission
from django.test import Client, RequestFactory
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User

pytestmark = pytest.mark.django_db


@pytest.fixture
def superuser():
    return User.objects.create_superuser(phone="+8801612345678",
                                         password="adminpass123")


@pytest.fixture
def staff():
    user = User.objects.create_user(phone="+8801712345678",
                                    password="staffpass123", is_staff=True)
    user.user_permissions.add(*Permission.objects.filter(
        codename__in=["change_user", "delete_user"]))
    return User.objects.get(pk=user.pk)


def _as(user):
    request = RequestFactory().get("/admin/")
    request.user = user
    return request


def test_admin_login_is_throttled_per_ip(superuser):
    client = Client()
    for _ in range(5):
        resp = client.post("/admin/login/", {"username": superuser.phone,
                                             "password": "wrong"})
        assert resp.status_code == 200

    blocked = client.post("/admin/login/", {"username": superuser.phone,
                                            "password": "adminpass123"})
    assert blocked.status_code == 429


def test_suspended_staff_are_shut_out_of_the_admin(superuser):
    superuser.suspended_at = timezone.now()
    superuser.save(update_fields=["suspended_at"])
    client = Client()
    client.force_login(superuser)

    resp = client.get("/admin/")
    assert resp.status_code == 302
    assert resp.url.startswith("/admin/login/")


def test_staff_cannot_grant_themselves_superuser(staff):
    user_admin = admin.site._registry[User]

    readonly = user_admin.get_readonly_fields(_as(staff), staff)
    assert {"is_staff", "is_superuser", "groups",
            "user_permissions"} <= set(readonly)


def test_staff_cannot_edit_or_delete_a_superuser(staff, superuser):
    user_admin = admin.site._registry[User]

    assert user_admin.has_change_permission(_as(staff), superuser) is False
    assert user_admin.has_delete_permission(_as(staff), superuser) is False
    assert user_admin.has_change_permission(_as(superuser), superuser)


def _code(device):
    from django_otp.oath import TOTP

    totp = TOTP(device.bin_key, device.step, device.t0, device.digits,
                device.drift)
    return "%06d" % totp.token()


def _password_login(client, user, password="adminpass123"):
    return client.post("/admin/login/?next=/admin/",
                       {"username": user.phone, "password": password,
                        "next": "/admin/"})


def test_password_alone_does_not_open_the_admin(superuser):
    client = Client()
    resp = _password_login(client, superuser)

    assert resp.status_code == 302
    assert resp.url == "/admin/two-factor/?next=%2Fadmin%2F"
    assert client.get("/admin/").status_code == 302


def test_first_login_enrols_an_authenticator_app(superuser):
    from django_otp.plugins.otp_totp.models import TOTPDevice

    client = Client()
    _password_login(client, superuser)
    page = client.get("/admin/two-factor/?next=/admin/")
    assert page.status_code == 200
    assert b"data:image/svg+xml;base64," in page.content

    device = TOTPDevice.objects.get(user=superuser)
    assert device.confirmed is False
    resp = client.post("/admin/two-factor/",
                       {"token": _code(device), "next": "/admin/"})

    assert resp.status_code == 302
    assert resp.url == "/admin/"
    device.refresh_from_db()
    assert device.confirmed is True
    assert client.get("/admin/").status_code == 200


def test_enrolled_staff_need_the_current_code(superuser):
    from django_otp.plugins.otp_totp.models import TOTPDevice

    device = TOTPDevice.objects.create(user=superuser, name="Phone",
                                       confirmed=True)
    client = Client()
    _password_login(client, superuser)

    page = client.get("/admin/two-factor/")
    assert b"data:image/svg+xml" not in page.content

    wrong = "000000" if _code(device) != "000000" else "111111"
    assert client.post("/admin/two-factor/",
                       {"token": wrong}).status_code == 200
    assert client.get("/admin/").status_code == 302

    device.throttle_reset()
    assert client.post("/admin/two-factor/",
                       {"token": _code(device)}).status_code == 302
    assert client.get("/admin/").status_code == 200


def test_two_factor_ignores_an_offsite_next(superuser):
    from django_otp.plugins.otp_totp.models import TOTPDevice

    device = TOTPDevice.objects.create(user=superuser, name="Phone",
                                       confirmed=True)
    client = Client()
    _password_login(client, superuser)
    resp = client.post("/admin/two-factor/",
                       {"token": _code(device),
                        "next": "https://evil.example/steal"})
    assert resp.status_code == 302
    assert resp.url == "/admin/"


def test_switching_account_from_the_two_factor_page_signs_out(superuser):
    client = Client()
    _password_login(client, superuser)
    resp = client.post("/admin/two-factor/", {"cancel": "1"})

    assert resp.status_code == 302
    assert "_auth_user_id" not in client.session


def test_staff_jwt_cannot_reach_the_admin_api(superuser):
    from rest_framework.test import APIClient

    client = APIClient()
    token = client.post("/api/v1/auth/login/",
                        {"phone": superuser.phone,
                         "password": "adminpass123"},
                        format="json").data["access"]
    client.credentials(HTTP_AUTHORIZATION="Bearer %s" % token)

    assert client.get("/api/v1/admin/verifications/").status_code == 403


def test_dashboard_shows_the_work_queues(superuser):
    from apps.common.testing import verified_admin_client

    resp = verified_admin_client(superuser, Client()).get("/admin/")
    assert resp.status_code == 200
    for title in (b"Verifications waiting", b"Open disputes",
                  b"Flagged payments", b"Oldest open disputes"):
        assert title in resp.content


def test_dashboard_only_shows_what_a_role_may_see(db):
    from django.contrib.auth.models import Group

    from apps.common.testing import verified_admin_client

    finance = User.objects.create_user(phone="+8801812345678",
                                       password="staffpass123",
                                       is_staff=True)
    finance.groups.add(Group.objects.get(name="Finance"))

    resp = verified_admin_client(finance, Client()).get("/admin/")
    assert resp.status_code == 200
    assert b"Flagged payments" in resp.content
    assert b"Verifications waiting" not in resp.content


def test_staff_roles_are_created_with_their_permissions(db):
    from django.contrib.auth.models import Group

    finance = Group.objects.get(name="Finance")
    codenames = set(finance.permissions.values_list("codename", flat=True))
    assert {"change_payment", "add_ledgerentry"} <= codenames
    assert "change_user" not in codenames
    assert set(Group.objects.values_list("name", flat=True)) >= {
        "Support", "Moderator", "Finance", "Catalogue editor"}


def test_only_superusers_edit_roles_and_nobody_edits_the_audit_log(staff):
    from django.contrib.admin.models import LogEntry
    from django.contrib.auth.models import Group

    staff.user_permissions.add(*Permission.objects.filter(
        codename__in=["change_group", "add_group", "change_logentry",
                      "delete_logentry"]))
    staff = User.objects.get(pk=staff.pk)

    group_admin = admin.site._registry[Group]
    log_admin = admin.site._registry[LogEntry]
    assert group_admin.has_change_permission(_as(staff)) is False
    assert group_admin.has_add_permission(_as(staff)) is False
    assert log_admin.has_change_permission(_as(staff)) is False
    assert log_admin.has_delete_permission(_as(staff)) is False


def test_every_admin_list_and_add_page_renders(superuser):
    from apps.common.testing import admin_session

    client = admin_session(superuser)
    for model, model_admin in admin.site._registry.items():
        meta = model._meta
        prefix = "admin:%s_%s" % (meta.app_label, meta.model_name)
        assert client.get(reverse(prefix + "_changelist")).status_code == 200, \
            meta.label
        if model_admin.has_add_permission(_as(superuser)):
            assert client.get(reverse(prefix + "_add")).status_code == 200, \
                meta.label


def test_staff_account_can_be_created_in_the_admin(superuser):
    from apps.common.testing import admin_session

    resp = admin_session(superuser).post(reverse("admin:accounts_user_add"), {
        "phone": "+8801812345678", "email": "", "full_name": "Support Agent",
        "password1": "a-Long-pass-2026", "password2": "a-Long-pass-2026",
    })

    assert resp.status_code == 302
    created = User.objects.get(phone="+8801812345678")
    assert created.check_password("a-Long-pass-2026")
    assert admin_session(superuser).get(reverse(
        "admin:accounts_user_change", args=[created.pk])).status_code == 200
