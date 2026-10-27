from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.bookings import services
from apps.bookings.models import Booking, BookingEvent, ServiceRequest

pytestmark = pytest.mark.django_db

State = Booking.State


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


def _create_request(client, service, location, future_window):
    start, end = future_window
    return client.post(reverse("bookings:requests"), {
        "service": service.id, "location": location.id,
        "address": "House 12, Road 5", "description": "AC not cooling",
        "preferred_start": start.isoformat(),
        "preferred_end": end.isoformat(),
    }, format="json")


def test_request_creation_requires_customer(anon, provider_client, service,
                                            dhanmondi, future_window):
    assert _create_request(anon, service, dhanmondi,
                           future_window).status_code == 401
    assert _create_request(provider_client, service, dhanmondi,
                           future_window).status_code == 403


def test_customer_creates_a_request(customer_client, provider, service,
                                    dhanmondi, future_window):
    resp = _create_request(customer_client, service, dhanmondi,
                           future_window)
    assert resp.status_code == 201
    assert resp.data["state"] == "open"
    assert resp.data["kind"] == "broadcast"


def test_request_in_the_past_is_rejected(customer_client, service,
                                         dhanmondi):
    past = timezone.now() - timezone.timedelta(days=1)
    resp = customer_client.post(reverse("bookings:requests"), {
        "service": service.id, "location": dhanmondi.id,
        "address": "x", "description": "y",
        "preferred_start": past.isoformat(),
        "preferred_end": (past + timezone.timedelta(hours=2)).isoformat(),
    }, format="json")

    assert resp.status_code == 400
    assert resp.data["error"]["code"] == "window_in_past"


def test_customer_sees_only_their_own_requests(customer_client, customer,
                                               provider, service, dhanmondi,
                                               future_window, db):
    from apps.accounts import services as account_services

    other = account_services.register_user(
        phone="+8801999999999", password="testpass123",
        role=User.Role.CUSTOMER,
    ).customer_profile
    start, end = future_window
    services.create_request(
        customer_id=other.id, service_id=service.id,
        location_id=dhanmondi.id, address="x", description="y",
        preferred_start=start, preferred_end=end,
    )
    _create_request(customer_client, service, dhanmondi, future_window)

    resp = customer_client.get(reverse("bookings:requests"))
    assert len(resp.data) == 1


def test_provider_inbox_shows_eligible_requests(provider_client,
                                                customer_client, provider,
                                                service, dhanmondi,
                                                future_window):
    _create_request(customer_client, service, dhanmondi, future_window)

    resp = provider_client.get(reverse("bookings:inbox"))
    assert resp.status_code == 200
    assert len(resp.data) == 1


def test_inbox_requires_provider(customer_client):
    assert customer_client.get(
        reverse("bookings:inbox")
    ).status_code == 403


def test_provider_accepts_and_creates_a_booking(provider_client,
                                                customer_client, provider,
                                                service, dhanmondi,
                                                future_window):
    created = _create_request(customer_client, service, dhanmondi,
                              future_window)
    request_id = created.data["id"]

    resp = provider_client.post(
        reverse("bookings:respond", args=[request_id]),
        {"accept": True}, format="json",
    )
    assert resp.status_code == 201
    assert resp.data["state"] == "scheduled"
    assert Decimal(resp.data["agreed_price"]) == Decimal("1800")


def test_provider_declines_without_creating_a_booking(
        provider_client, customer_client, provider, service, dhanmondi,
        future_window):
    created = _create_request(customer_client, service, dhanmondi,
                              future_window)
    resp = provider_client.post(
        reverse("bookings:respond", args=[created.data["id"]]),
        {"accept": False, "reason": "Fully booked"}, format="json",
    )
    assert resp.status_code == 200
    assert resp.data["accepted"] is False
    assert not Booking.objects.exists()


def test_customer_cannot_respond_to_a_request(customer_client, provider,
                                              service, dhanmondi,
                                              future_window):
    created = _create_request(customer_client, service, dhanmondi,
                              future_window)
    resp = customer_client.post(
        reverse("bookings:respond", args=[created.data["id"]]),
        {"accept": True}, format="json",
    )
    assert resp.status_code == 403


def test_full_lifecycle_through_the_api(provider_client, customer_client,
                                        provider, service, dhanmondi,
                                        future_window,
                                        django_capture_on_commit_callbacks):
    created = _create_request(customer_client, service, dhanmondi,
                              future_window)
    accepted = provider_client.post(
        reverse("bookings:respond", args=[created.data["id"]]),
        {"accept": True}, format="json",
    )
    booking_id = accepted.data["id"]

    started = provider_client.post(
        reverse("bookings:booking-start", args=[booking_id])
    )
    assert started.data["state"] == "in_progress"

    completed = provider_client.post(
        reverse("bookings:booking-complete", args=[booking_id]),
        {"final_price": "2000"}, format="json",
    )
    assert completed.data["state"] == "awaiting_confirm"

    with django_capture_on_commit_callbacks(execute=True):
        confirmed = customer_client.post(
            reverse("bookings:booking-confirm", args=[booking_id]),
            {"confirmed_price": "2000"}, format="json",
        )
    assert confirmed.data["state"] == "completed"


def test_customer_cannot_start_a_job(customer_client, provider_client,
                                     provider, service, dhanmondi,
                                     future_window):
    created = _create_request(customer_client, service, dhanmondi,
                              future_window)
    accepted = provider_client.post(
        reverse("bookings:respond", args=[created.data["id"]]),
        {"accept": True}, format="json",
    )

    resp = customer_client.post(
        reverse("bookings:booking-start", args=[accepted.data["id"]])
    )
    assert resp.status_code == 403


def test_provider_cannot_confirm_their_own_completion(
        provider_client, customer_client, provider, service, dhanmondi,
        future_window):
    created = _create_request(customer_client, service, dhanmondi,
                              future_window)
    accepted = provider_client.post(
        reverse("bookings:respond", args=[created.data["id"]]),
        {"accept": True}, format="json",
    )
    booking_id = accepted.data["id"]
    provider_client.post(reverse("bookings:booking-start",
                                 args=[booking_id]))
    provider_client.post(reverse("bookings:booking-complete",
                                 args=[booking_id]), {}, format="json")

    resp = provider_client.post(
        reverse("bookings:booking-confirm", args=[booking_id]),
        {}, format="json",
    )
    assert resp.status_code == 403


def test_illegal_transition_returns_409(provider_client, customer_client,
                                        provider, service, dhanmondi,
                                        future_window):
    created = _create_request(customer_client, service, dhanmondi,
                              future_window)
    accepted = provider_client.post(
        reverse("bookings:respond", args=[created.data["id"]]),
        {"accept": True}, format="json",
    )

    resp = customer_client.post(
        reverse("bookings:booking-confirm", args=[accepted.data["id"]]),
        {}, format="json",
    )
    assert resp.status_code == 409
    assert resp.data["error"]["code"] == "invalid_state_transition"


def test_booking_detail_shows_the_event_timeline(
        provider_client, customer_client, provider, service, dhanmondi,
        future_window):
    created = _create_request(customer_client, service, dhanmondi,
                              future_window)
    accepted = provider_client.post(
        reverse("bookings:respond", args=[created.data["id"]]),
        {"accept": True}, format="json",
    )
    booking_id = accepted.data["id"]
    provider_client.post(reverse("bookings:booking-start",
                                 args=[booking_id]))

    resp = customer_client.get(
        reverse("bookings:booking-detail", args=[booking_id])
    )
    assert resp.status_code == 200
    assert [e["to_state"] for e in resp.data["events"]] == [
        "scheduled", "in_progress",
    ]


def test_outsider_cannot_read_a_booking(provider_client, customer_client,
                                        provider, service, dhanmondi,
                                        future_window, db):
    from apps.accounts import services as account_services

    created = _create_request(customer_client, service, dhanmondi,
                              future_window)
    accepted = provider_client.post(
        reverse("bookings:respond", args=[created.data["id"]]),
        {"accept": True}, format="json",
    )

    outsider = account_services.register_user(
        phone="+8801999999999", password="testpass123",
        role=User.Role.CUSTOMER,
    )
    resp = _auth(outsider).get(
        reverse("bookings:booking-detail", args=[accepted.data["id"]])
    )
    assert resp.status_code == 404


def test_cancel_requires_a_reason(provider_client, customer_client, provider,
                                  service, dhanmondi, future_window):
    created = _create_request(customer_client, service, dhanmondi,
                              future_window)
    accepted = provider_client.post(
        reverse("bookings:respond", args=[created.data["id"]]),
        {"accept": True}, format="json",
    )

    resp = customer_client.post(
        reverse("bookings:booking-cancel", args=[accepted.data["id"]]),
        {}, format="json",
    )
    assert resp.status_code == 400


def test_customer_cancels_a_booking(provider_client, customer_client,
                                    provider, service, dhanmondi,
                                    future_window):
    created = _create_request(customer_client, service, dhanmondi,
                              future_window)
    accepted = provider_client.post(
        reverse("bookings:respond", args=[created.data["id"]]),
        {"accept": True}, format="json",
    )

    resp = customer_client.post(
        reverse("bookings:booking-cancel", args=[accepted.data["id"]]),
        {"reason": "Plans changed"}, format="json",
    )
    assert resp.status_code == 200
    assert resp.data["state"] == "cancelled_customer"
    assert resp.data["cancel_reason"] == "Plans changed"


def test_withdraw_an_open_request(customer_client, provider, service,
                                  dhanmondi, future_window):
    created = _create_request(customer_client, service, dhanmondi,
                              future_window)
    resp = customer_client.post(
        reverse("bookings:request-withdraw", args=[created.data["id"]]),
        {"reason": "Fixed it myself"}, format="json",
    )
    assert resp.status_code == 200
    assert resp.data["state"] == "withdrawn"


def test_request_detail_lists_responses(customer_client, provider_client,
                                        provider, service, dhanmondi,
                                        future_window):
    created = _create_request(customer_client, service, dhanmondi,
                              future_window)
    provider_client.post(
        reverse("bookings:respond", args=[created.data["id"]]),
        {"accept": False, "reason": "Busy"}, format="json",
    )

    resp = customer_client.get(
        reverse("bookings:request-detail", args=[created.data["id"]])
    )
    assert len(resp.data["responses"]) == 1
    assert resp.data["responses"][0]["decision"] == "declined"


def test_inbox_withholds_the_address_before_acceptance(
        provider_client, customer_client, provider, service, dhanmondi,
        future_window):
    _create_request(customer_client, service, dhanmondi, future_window)

    resp = provider_client.get(reverse("bookings:inbox"))
    row = resp.data[0]
    assert "address" not in row
    assert "House 12" not in str(resp.data)
    assert row["location_detail"]["name"] == "Dhanmondi"


def test_customer_still_sees_their_own_address(customer_client, provider,
                                               service, dhanmondi,
                                               future_window):
    created = _create_request(customer_client, service, dhanmondi,
                              future_window)
    assert created.data["address"] == "House 12, Road 5"


def test_accepted_provider_gets_customer_contact(
        provider_client, customer_client, provider, service, dhanmondi,
        future_window):
    created = _create_request(customer_client, service, dhanmondi,
                              future_window)
    accepted = provider_client.post(
        reverse("bookings:respond", args=[created.data["id"]]),
        {"accept": True}, format="json",
    )

    resp = provider_client.get(
        reverse("bookings:booking-detail", args=[accepted.data["id"]])
    )
    assert resp.data["address"] == "House 12, Road 5"
    assert resp.data["customer_name"] == "Rumana Akter"
    assert resp.data["customer_phone"] == "+8801912345678"


def test_booking_detail_reports_review_progress(
        provider_client, customer_client, provider, service, dhanmondi,
        future_window):
    created = _create_request(customer_client, service, dhanmondi,
                              future_window)
    accepted = provider_client.post(
        reverse("bookings:respond", args=[created.data["id"]]),
        {"accept": True}, format="json",
    )

    resp = customer_client.get(
        reverse("bookings:booking-detail", args=[accepted.data["id"]])
    )
    assert resp.data["review_submitted"] is False
    assert resp.data["customer_rated"] is False


def test_request_creation_is_rate_limited_per_customer(customer_client,
                                                       service, dhanmondi,
                                                       future_window):
    for _ in range(10):
        assert _create_request(customer_client, service, dhanmondi,
                               future_window).status_code == 201

    assert _create_request(customer_client, service, dhanmondi,
                           future_window).status_code == 429
    assert customer_client.get(reverse("bookings:requests")).status_code == 200
