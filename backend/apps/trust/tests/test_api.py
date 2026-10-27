import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts import services as account_services
from apps.accounts.models import User
from apps.common.testing import verified_admin_client
from apps.trust import engine
from apps.trust.models import TrustSnapshot

pytestmark = pytest.mark.django_db


def _auth(user, password="testpass123"):
    client = APIClient()
    resp = client.post(reverse("accounts:login"),
                       {"phone": user.phone, "password": password},
                       format="json")
    client.credentials(HTTP_AUTHORIZATION="Bearer %s" % resp.data["access"])
    return client


@pytest.fixture
def anon():
    return APIClient()


@pytest.fixture
def provider_user(db):
    return account_services.register_user(
        phone="+8801712345678", password="testpass123",
        full_name="Kamal Hossain", role=User.Role.PROVIDER,
    )


@pytest.fixture
def provider(provider_user):
    return provider_user.provider_profile


@pytest.fixture
def customer_user(db):
    return account_services.register_user(
        phone="+8801912345678", password="testpass123",
        role=User.Role.CUSTOMER,
    )


@pytest.fixture
def admin_user(db):
    return User.objects.create_superuser(
        phone="+8801611112222", password="adminpass123",
    )


def test_trust_breakdown_is_public(anon, provider):
    resp = anon.get(reverse("trust:provider-trust", args=[provider.id]))
    assert resp.status_code == 200
    assert "score" in resp.data and "tier" in resp.data


def test_breakdown_shows_factors_not_just_a_score(anon, provider):
    resp = anon.get(reverse("trust:provider-trust", args=[provider.id]))
    assert len(resp.data["factors"]) == 6
    assert "verification" in resp.data
    assert "evidence" in resp.data


def test_breakdown_unknown_provider_uses_error_envelope(anon):
    resp = anon.get(reverse("trust:provider-trust", args=[99999]))
    assert resp.status_code == 404
    assert resp.data["error"]["code"] == "provider_not_found"


def test_trust_history_requires_provider_role(anon, customer_user):
    assert anon.get(
        reverse("trust:my-trust-history")
    ).status_code == 401

    client = _auth(customer_user)
    assert client.get(
        reverse("trust:my-trust-history")
    ).status_code == 403


def test_provider_sees_own_history(provider_user, provider):
    engine.recompute(provider.id)
    engine.recompute(provider.id)

    client = _auth(provider_user)
    resp = client.get(reverse("trust:my-trust-history"))
    assert resp.status_code == 200
    assert resp.data["count"] == 2


def test_provider_history_excludes_other_providers(provider_user, provider,
                                                    db):
    other = account_services.register_user(
        phone="+8801812345678", password="testpass123",
        role=User.Role.PROVIDER,
    ).provider_profile
    engine.recompute(other.id)
    engine.recompute(provider.id)

    client = _auth(provider_user)
    resp = client.get(reverse("trust:my-trust-history"))
    assert resp.data["count"] == 1


def test_audit_requires_admin(provider_user, provider):
    client = _auth(provider_user)
    resp = client.get(reverse("trust:trust-audit", args=[provider.id]))
    assert resp.status_code == 403


def test_admin_audit_exposes_factor_inputs(admin_user, provider):
    engine.recompute(provider.id)

    client = verified_admin_client(admin_user)
    resp = client.get(reverse("trust:trust-audit", args=[provider.id]))

    assert resp.status_code == 200
    assert "factors" in resp.data["results"][0]
    assert "weights" in resp.data["results"][0]["factors"]


def test_provider_history_hides_factor_inputs(provider_user, provider):
    engine.recompute(provider.id)

    client = _auth(provider_user)
    resp = client.get(reverse("trust:my-trust-history"))
    assert "factors" not in resp.data["results"][0]


def test_admin_can_force_recompute(admin_user, provider):
    client = verified_admin_client(admin_user)
    resp = client.post(
        reverse("trust:trust-recompute", args=[provider.id])
    )
    assert resp.status_code == 200
    assert resp.data["trigger"] == TrustSnapshot.Trigger.MANUAL


def test_provider_cannot_force_recompute(provider_user, provider):
    client = _auth(provider_user)
    resp = client.post(
        reverse("trust:trust-recompute", args=[provider.id])
    )
    assert resp.status_code == 403
    assert not TrustSnapshot.objects.exists()


def test_trust_score_is_not_writable_through_provider_api(provider_user,
                                                           provider):
    client = _auth(provider_user)
    client.patch(reverse("providers:my-profile"),
                 {"trust_score": "99.00", "trust_tier": "trusted_pro"},
                 format="json")
    provider.refresh_from_db()
    assert provider.trust_score == 0
