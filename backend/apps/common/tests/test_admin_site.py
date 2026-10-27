import pytest
from django.contrib import admin
from django.contrib.auth.models import Permission
from django.test import Client, RequestFactory
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
