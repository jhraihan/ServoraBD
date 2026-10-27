import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts import services
from apps.accounts.models import PhoneOTP

User = get_user_model()
pytestmark = pytest.mark.django_db

PHONE = "+8801712345678"
PASSWORD = "testpass123"

@pytest.fixture
def client():
    return APIClient()

@pytest.fixture
def user():
    return services.register_user(
        phone=PHONE, password=PASSWORD, full_name="Rumana A.",
    )

@pytest.fixture
def auth_client(client, user):
    resp = client.post(reverse("accounts:login"),
                       {"phone": PHONE, "password": PASSWORD}, format="json")
    client.credentials(HTTP_AUTHORIZATION="Bearer %s" % resp.data["access"])
    return client

def test_register_returns_201_and_user(client):
    resp = client.post(reverse("accounts:register"), {
        "phone": "01712345678", "password": PASSWORD, "full_name": "Rumana",
    }, format="json")

    assert resp.status_code == 201
    assert resp.data["user"]["phone"] == PHONE
    assert resp.data["otp_sent"] is True
    assert "password" not in resp.data["user"]

def test_register_sends_otp_automatically(client):
    client.post(reverse("accounts:register"),
                {"phone": PHONE, "password": PASSWORD}, format="json")
    assert PhoneOTP.objects.filter(phone=PHONE).count() == 1

def test_register_duplicate_returns_error_envelope(client, user):
    resp = client.post(reverse("accounts:register"),
                       {"phone": PHONE, "password": PASSWORD}, format="json")

    assert resp.status_code == 400
    assert resp.data["error"]["code"] == "phone_taken"
    assert "message" in resp.data["error"]

def test_register_short_password_rejected(client):
    resp = client.post(reverse("accounts:register"),
                       {"phone": PHONE, "password": "short"}, format="json")
    assert resp.status_code == 400
    assert resp.data["error"]["code"] == "validation_error"

def test_register_as_provider(client):
    resp = client.post(reverse("accounts:register"), {
        "phone": PHONE, "password": PASSWORD,
        "full_name": "Kamal H.", "role": "provider",
    }, format="json")

    assert resp.status_code == 201
    assert resp.data["user"]["provider_profile"] is not None
    assert resp.data["user"]["provider_profile"]["trust_tier"] == "new"

def test_otp_verify_flow(client, user, monkeypatch):
    monkeypatch.setattr(PhoneOTP, "generate_code",
                        staticmethod(lambda: "123456"))
    client.post(reverse("accounts:otp-send"), {"phone": PHONE}, format="json")

    resp = client.post(reverse("accounts:otp-verify"),
                       {"phone": PHONE, "code": "123456"}, format="json")

    assert resp.status_code == 200
    assert resp.data["verified"] is True
    user.refresh_from_db()
    assert user.phone_verified is True

def test_otp_wrong_code_reports_remaining_attempts(client, user, monkeypatch):
    monkeypatch.setattr(PhoneOTP, "generate_code",
                        staticmethod(lambda: "123456"))
    client.post(reverse("accounts:otp-send"), {"phone": PHONE}, format="json")

    resp = client.post(reverse("accounts:otp-verify"),
                       {"phone": PHONE, "code": "000000"}, format="json")

    assert resp.status_code == 400
    assert resp.data["error"]["code"] == "otp_mismatch"
    assert resp.data["error"]["details"]["attempts_remaining"] == 4

def test_otp_rate_limit_returns_429(client):
    url = reverse("accounts:otp-send")
    for _ in range(3):
        client.post(url, {"phone": PHONE}, format="json")

    resp = client.post(url, {"phone": PHONE}, format="json")
    assert resp.status_code == 429
    assert resp.data["error"]["code"] == "rate_limited"

def test_login_returns_token_pair_with_roles(client, user):
    resp = client.post(reverse("accounts:login"),
                       {"phone": PHONE, "password": PASSWORD}, format="json")

    assert resp.status_code == 200
    assert "access" in resp.data and "refresh" in resp.data
    assert resp.data["user"]["roles"] == ["customer"]

def test_login_works_with_local_phone_format(client, user):
    resp = client.post(reverse("accounts:login"),
                       {"phone": "01712345678", "password": PASSWORD},
                       format="json")
    assert resp.status_code == 200

def test_login_with_email_only_account(client):
    services.register_user(email="k@example.com", password=PASSWORD)
    resp = client.post(reverse("accounts:login"),
                       {"phone": "k@example.com", "password": PASSWORD},
                       format="json")
    assert resp.status_code == 200

def test_login_wrong_password_rejected(client, user):
    resp = client.post(reverse("accounts:login"),
                       {"phone": PHONE, "password": "wrongpass"},
                       format="json")
    assert resp.status_code == 401

def test_suspended_account_cannot_log_in(client, user):
    from django.utils import timezone
    user.suspended_at = timezone.now()
    user.save(update_fields=["suspended_at"])

    resp = client.post(reverse("accounts:login"),
                       {"phone": PHONE, "password": PASSWORD}, format="json")
    assert resp.status_code == 400

def test_me_requires_authentication(client):
    assert client.get(reverse("accounts:me")).status_code == 401

def test_me_returns_current_user(auth_client):
    resp = auth_client.get(reverse("accounts:me"))
    assert resp.status_code == 200
    assert resp.data["phone"] == PHONE

def test_me_cannot_change_readonly_fields(auth_client, user):
    resp = auth_client.patch(reverse("accounts:me"),
                             {"phone_verified": True, "full_name": "Changed"},
                             format="json")
    assert resp.status_code == 200
    user.refresh_from_db()
    assert user.full_name == "Changed"
    assert user.phone_verified is False

def test_switch_role_denied_without_profile(auth_client):
    resp = auth_client.post(reverse("accounts:switch-role"),
                            {"role": "provider"}, format="json")
    assert resp.status_code == 400
    assert resp.data["error"]["code"] == "role_not_held"

def test_add_profile_then_switch(auth_client):
    add = auth_client.post(reverse("accounts:add-profile"),
                           {"role": "provider"}, format="json")
    assert add.status_code == 201

    resp = auth_client.post(reverse("accounts:switch-role"),
                            {"role": "provider"}, format="json")
    assert resp.status_code == 200
    assert resp.data["active_role"] == "provider"
    assert set(resp.data["roles"]) == {"customer", "provider"}

def test_provider_trust_fields_are_not_writable(auth_client):
    auth_client.post(reverse("accounts:add-profile"), {"role": "provider"},
                     format="json")
    resp = auth_client.get(reverse("accounts:me"))

    profile = resp.data["provider_profile"]
    assert profile["trust_score"] == "0.00"
    assert profile["identity_verified"] is False

def test_logout_blacklists_refresh_token(client, user):
    login = client.post(reverse("accounts:login"),
                        {"phone": PHONE, "password": PASSWORD}, format="json")
    refresh = login.data["refresh"]
    client.credentials(HTTP_AUTHORIZATION="Bearer %s" % login.data["access"])

    resp = client.post(reverse("accounts:logout"), {"refresh": refresh},
                       format="json")
    assert resp.status_code == 204

    again = client.post(reverse("token-refresh"), {"refresh": refresh},
                        format="json")
    assert again.status_code == 401

def test_logout_requires_refresh_token(auth_client):
    resp = auth_client.post(reverse("accounts:logout"), {}, format="json")
    assert resp.status_code == 400
    assert resp.data["error"]["code"] == "refresh_required"

def test_login_throttled_after_five_attempts(client, user):
    url = reverse("accounts:login")
    for _ in range(5):
        resp = client.post(url, {"phone": PHONE, "password": "wrongpass"},
                           format="json")
        assert resp.status_code == 401

    blocked = client.post(url, {"phone": PHONE, "password": PASSWORD},
                          format="json")
    assert blocked.status_code == 429

def test_throttle_counts_attempts_not_identifiers(client, user):
    url = reverse("accounts:login")
    for i in range(5):
        client.post(url, {"phone": "+88017123456%02d" % i,
                          "password": "wrongpass"}, format="json")

    blocked = client.post(url, {"phone": PHONE, "password": PASSWORD},
                          format="json")
    assert blocked.status_code == 429


def test_login_throttle_cannot_be_bypassed_with_forwarded_for(client, user):
    url = reverse("accounts:login")
    for i in range(5):
        client.post(url, {"phone": PHONE, "password": "wrongpass"},
                    format="json", HTTP_X_FORWARDED_FOR="203.0.113.%d" % i)

    spoofed = client.post(url, {"phone": PHONE, "password": PASSWORD},
                          format="json", HTTP_X_FORWARDED_FOR="198.51.100.77")
    assert spoofed.status_code == 429


@pytest.fixture
def behind_one_proxy(settings):
    settings.REST_FRAMEWORK = {**settings.REST_FRAMEWORK, "NUM_PROXIES": 1}


def test_behind_nginx_only_the_proxy_appended_address_counts(
        client, user, behind_one_proxy):
    url = reverse("accounts:login")
    for i in range(5):
        client.post(url, {"phone": PHONE, "password": "wrongpass"},
                    format="json",
                    HTTP_X_FORWARDED_FOR="203.0.113.%d, 192.0.2.10" % i)

    same_client = client.post(url, {"phone": PHONE, "password": PASSWORD},
                              format="json",
                              HTTP_X_FORWARDED_FOR="198.51.100.1, 192.0.2.10")
    assert same_client.status_code == 429


def test_behind_nginx_different_clients_keep_separate_budgets(
        client, user, behind_one_proxy):
    url = reverse("accounts:login")
    for _ in range(5):
        client.post(url, {"phone": PHONE, "password": "wrongpass"},
                    format="json", HTTP_X_FORWARDED_FOR="192.0.2.10")

    other_client = client.post(url, {"phone": PHONE, "password": PASSWORD},
                               format="json",
                               HTTP_X_FORWARDED_FOR="192.0.2.99")
    assert other_client.status_code == 200


def test_registration_is_rate_limited_per_ip(client):
    url = reverse("accounts:register")
    for n in range(10):
        resp = client.post(url, {"email": "user%d@example.com" % n,
                                 "password": PASSWORD}, format="json")
        assert resp.status_code == 201

    blocked = client.post(url, {"email": "user99@example.com",
                                "password": PASSWORD}, format="json")
    assert blocked.status_code == 429


def test_otp_sending_is_rate_limited_per_ip_across_numbers(client):
    url = reverse("accounts:otp-send")
    for n in range(10):
        resp = client.post(url, {"phone": "+88017123456%02d" % n},
                           format="json")
        assert resp.status_code == 200

    blocked = client.post(url, {"phone": "+8801812345678"}, format="json")
    assert blocked.status_code == 429


def _suspend(user):
    from django.utils import timezone
    user.suspended_at = timezone.now()
    user.save(update_fields=["suspended_at"])


def test_suspension_revokes_an_access_token_already_issued(auth_client, user):
    _suspend(user)

    resp = auth_client.get(reverse("accounts:me"))
    assert resp.status_code == 401
    assert resp.data["error"]["code"] == "user_suspended"


def test_suspended_account_cannot_refresh_its_token(client, user):
    login = client.post(reverse("accounts:login"),
                        {"phone": PHONE, "password": PASSWORD}, format="json")
    _suspend(user)

    resp = client.post(reverse("token-refresh"),
                       {"refresh": login.data["refresh"]}, format="json")
    assert resp.status_code == 401
    assert resp.data["error"]["code"] == "user_suspended"


def test_active_role_cannot_be_set_through_me(auth_client, user):
    resp = auth_client.patch(reverse("accounts:me"),
                             {"active_role": "admin"}, format="json")
    assert resp.status_code == 200
    user.refresh_from_db()
    assert user.active_role == User.Role.CUSTOMER
