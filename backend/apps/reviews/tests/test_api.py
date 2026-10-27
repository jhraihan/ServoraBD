import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.common.testing import verified_admin_client
from apps.reviews import services
from apps.reviews.models import Review

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
def customer_client(customer_user):
    return _auth(customer_user)


@pytest.fixture
def provider_client(provider_user):
    client = _auth(provider_user)
    client.post(reverse("accounts:switch-role"), {"role": "provider"},
                format="json")
    return client


@pytest.fixture
def admin_client(admin_user):
    return verified_admin_client(admin_user)


def test_review_creation_requires_customer(anon, provider_client,
                                           completed_booking):
    payload = {"booking": completed_booking.id, "rating": 5}
    assert anon.post(reverse("reviews:reviews"), payload,
                     format="json").status_code == 401
    assert provider_client.post(reverse("reviews:reviews"), payload,
                                format="json").status_code == 403


def test_customer_creates_a_review(customer_client, completed_booking):
    resp = customer_client.post(reverse("reviews:reviews"), {
        "booking": completed_booking.id, "rating": 5, "punctuality": 5,
        "quality": 4, "professionalism": 5, "price_fairness": 4,
        "comment": "Quick and tidy.",
    }, format="json")

    assert resp.status_code == 201
    assert resp.data["rating"] == 5
    assert resp.data["is_published"] is False


def test_rating_outside_range_rejected(customer_client, completed_booking):
    resp = customer_client.post(reverse("reviews:reviews"), {
        "booking": completed_booking.id, "rating": 6,
    }, format="json")
    assert resp.status_code == 400


def test_duplicate_review_returns_error_envelope(customer_client,
                                                 completed_booking):
    payload = {"booking": completed_booking.id, "rating": 5}
    customer_client.post(reverse("reviews:reviews"), payload, format="json")
    resp = customer_client.post(reverse("reviews:reviews"), payload,
                                format="json")

    assert resp.status_code == 400
    assert resp.data["error"]["code"] == "already_reviewed"


def test_unpublished_review_is_hidden_from_the_public(
        anon, customer_client, provider, completed_booking):
    customer_client.post(reverse("reviews:reviews"), {
        "booking": completed_booking.id, "rating": 5,
    }, format="json")

    resp = anon.get(reverse("reviews:provider-reviews", args=[provider.id]))
    assert resp.status_code == 200
    assert resp.data["count"] == 0


def test_review_appears_publicly_once_both_sides_submit(
        anon, customer_client, provider_client, provider, completed_booking,
        django_capture_on_commit_callbacks):
    customer_client.post(reverse("reviews:reviews"), {
        "booking": completed_booking.id, "rating": 5,
        "comment": "Excellent work",
    }, format="json")

    with django_capture_on_commit_callbacks(execute=True):
        provider_client.post(reverse("reviews:rate-customer"), {
            "booking": completed_booking.id, "rating": 5,
        }, format="json")

    resp = anon.get(reverse("reviews:provider-reviews", args=[provider.id]))
    assert resp.data["count"] == 1
    assert resp.data["results"][0]["comment"] == "Excellent work"


def test_public_review_does_not_leak_full_customer_name(
        anon, customer_client, provider_client, provider, completed_booking,
        django_capture_on_commit_callbacks):
    customer_client.post(reverse("reviews:reviews"), {
        "booking": completed_booking.id, "rating": 5,
    }, format="json")
    with django_capture_on_commit_callbacks(execute=True):
        provider_client.post(reverse("reviews:rate-customer"), {
            "booking": completed_booking.id, "rating": 5,
        }, format="json")

    resp = anon.get(reverse("reviews:provider-reviews", args=[provider.id]))
    name = resp.data["results"][0]["customer_name"]
    assert name == "Rumana A."


def test_customer_sees_own_review_before_publication(customer_client,
                                                     completed_booking):
    customer_client.post(reverse("reviews:reviews"), {
        "booking": completed_booking.id, "rating": 5,
    }, format="json")

    resp = customer_client.get(reverse("reviews:reviews"))
    assert len(resp.data) == 1
    assert resp.data[0]["is_published"] is False


def test_edit_own_review(customer_client, completed_booking):
    created = customer_client.post(reverse("reviews:reviews"), {
        "booking": completed_booking.id, "rating": 2, "comment": "Slow",
    }, format="json")

    resp = customer_client.patch(
        reverse("reviews:review-edit", args=[created.data["id"]]),
        {"rating": 4, "comment": "Slow but thorough"}, format="json",
    )
    assert resp.status_code == 200
    assert resp.data["rating"] == 4
    assert resp.data["was_edited"] is True


def test_edit_after_window_returns_error(customer_client,
                                         completed_booking):
    created = customer_client.post(reverse("reviews:reviews"), {
        "booking": completed_booking.id, "rating": 2,
    }, format="json")
    Review.objects.filter(pk=created.data["id"]).update(
        created_at=timezone.now() - timezone.timedelta(hours=25),
    )

    resp = customer_client.patch(
        reverse("reviews:review-edit", args=[created.data["id"]]),
        {"rating": 5}, format="json",
    )
    assert resp.status_code == 400
    assert resp.data["error"]["code"] == "edit_window_closed"


def test_customer_cannot_edit_another_customers_review(
        customer_client, completed_booking, db):
    from apps.accounts import services as account_services
    from apps.accounts.models import User

    created = customer_client.post(reverse("reviews:reviews"), {
        "booking": completed_booking.id, "rating": 5,
    }, format="json")

    other = account_services.register_user(
        phone="+8801999999999", password="testpass123",
        role=User.Role.CUSTOMER,
    )
    resp = _auth(other).patch(
        reverse("reviews:review-edit", args=[created.data["id"]]),
        {"rating": 1}, format="json",
    )
    assert resp.status_code == 404


def test_provider_replies_to_a_published_review(
        customer_client, provider_client, completed_booking,
        django_capture_on_commit_callbacks):
    created = customer_client.post(reverse("reviews:reviews"), {
        "booking": completed_booking.id, "rating": 5,
    }, format="json")
    with django_capture_on_commit_callbacks(execute=True):
        provider_client.post(reverse("reviews:rate-customer"), {
            "booking": completed_booking.id, "rating": 5,
        }, format="json")

    resp = provider_client.post(
        reverse("reviews:review-reply", args=[created.data["id"]]),
        {"body": "Thank you!"}, format="json",
    )
    assert resp.status_code == 201
    assert resp.data["reply"]["body"] == "Thank you!"


def test_customer_cannot_reply(customer_client, completed_booking):
    created = customer_client.post(reverse("reviews:reviews"), {
        "booking": completed_booking.id, "rating": 5,
    }, format="json")

    resp = customer_client.post(
        reverse("reviews:review-reply", args=[created.data["id"]]),
        {"body": "Hi"}, format="json",
    )
    assert resp.status_code == 403


def test_hide_requires_admin(customer_client, provider_client,
                             completed_booking):
    created = customer_client.post(reverse("reviews:reviews"), {
        "booking": completed_booking.id, "rating": 1,
    }, format="json")

    resp = provider_client.post(
        reverse("reviews:review-hide", args=[created.data["id"]]),
        {"reason": "Unfair"}, format="json",
    )
    assert resp.status_code == 403


def test_admin_hides_a_review(customer_client, admin_client, anon, provider,
                              provider_client, completed_booking,
                              django_capture_on_commit_callbacks):
    created = customer_client.post(reverse("reviews:reviews"), {
        "booking": completed_booking.id, "rating": 1,
        "comment": "Abusive text",
    }, format="json")
    with django_capture_on_commit_callbacks(execute=True):
        provider_client.post(reverse("reviews:rate-customer"), {
            "booking": completed_booking.id, "rating": 5,
        }, format="json")

    with django_capture_on_commit_callbacks(execute=True):
        resp = admin_client.post(
            reverse("reviews:review-hide", args=[created.data["id"]]),
            {"reason": "Abusive language"}, format="json",
        )
    assert resp.status_code == 200

    public = anon.get(
        reverse("reviews:provider-reviews", args=[provider.id])
    )
    assert public.data["count"] == 0


def test_provider_sees_reviews_received(provider_client, customer_client,
                                        completed_booking,
                                        django_capture_on_commit_callbacks):
    customer_client.post(reverse("reviews:reviews"), {
        "booking": completed_booking.id, "rating": 4,
    }, format="json")
    with django_capture_on_commit_callbacks(execute=True):
        provider_client.post(reverse("reviews:rate-customer"), {
            "booking": completed_booking.id, "rating": 5,
        }, format="json")

    resp = provider_client.get(reverse("reviews:my-reviews"))
    assert resp.data["count"] == 1


def test_trust_breakdown_reflects_published_reviews(
        anon, customer_client, provider_client, provider, completed_booking,
        django_capture_on_commit_callbacks):
    before = anon.get(
        reverse("trust:provider-trust", args=[provider.id])
    ).data["score"]

    customer_client.post(reverse("reviews:reviews"), {
        "booking": completed_booking.id, "rating": 5,
    }, format="json")
    with django_capture_on_commit_callbacks(execute=True):
        provider_client.post(reverse("reviews:rate-customer"), {
            "booking": completed_booking.id, "rating": 5,
        }, format="json")

    after = anon.get(
        reverse("trust:provider-trust", args=[provider.id])
    ).data["score"]
    assert after > before
