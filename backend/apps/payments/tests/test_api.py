from decimal import Decimal

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.common.testing import verified_admin_client
from apps.payments.models import LedgerEntry, Payment

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


def test_earnings_require_a_provider(anon, customer_client):
    assert anon.get(reverse("payments:earnings")).status_code == 401
    assert customer_client.get(
        reverse("payments:earnings")
    ).status_code == 403


def test_earnings_report_money_as_strings(provider_client, complete_job):
    complete_job(final_price="2000")
    complete_job(final_price="1500")

    resp = provider_client.get(reverse("payments:earnings"))
    summary = resp.data["summary"]

    assert resp.status_code == 200
    assert resp.data["currency"] == "BDT"
    assert summary["gross"] == "3500.00"
    assert summary["commission"] == "420.00"
    assert summary["net"] == "3080.00"
    assert summary["outstanding_payable"] == "420.00"
    assert summary["jobs"] == 2
    assert len(resp.data["periods"]) == 1


def test_earnings_period_parameter(provider_client, complete_job):
    complete_job(final_price="2000")
    resp = provider_client.get(reverse("payments:earnings"),
                               {"period": "day"})
    assert resp.data["period"] == "day"
    assert resp.data["periods"][0]["gross"] == "2000.00"


def test_earnings_ignore_an_unknown_period(provider_client, complete_job):
    complete_job(final_price="2000")
    resp = provider_client.get(reverse("payments:earnings"),
                               {"period": "fortnight", "start": "garbage"})
    assert resp.status_code == 200
    assert resp.data["period"] == "month"
    assert resp.data["start"] is None


def test_ledger_lists_entries(provider_client, complete_job):
    complete_job(final_price="2000")

    resp = provider_client.get(reverse("payments:ledger"))
    assert resp.data["count"] == 3

    only = provider_client.get(reverse("payments:ledger"),
                               {"kind": "commission"})
    assert only.data["count"] == 1
    assert only.data["results"][0]["amount"] == "-240.00"


def test_provider_sees_only_their_own_ledger(provider_client, complete_job,
                                             db):
    from apps.accounts import services as account_services
    from apps.accounts.models import User

    complete_job(final_price="2000")
    stranger = account_services.register_user(
        phone="+8801888888888", password="testpass123",
        role=User.Role.PROVIDER,
    )
    client = _auth(stranger)
    client.post(reverse("accounts:switch-role"), {"role": "provider"},
                format="json")

    assert client.get(reverse("payments:ledger")).data["count"] == 0
    assert provider_client.get(
        reverse("payments:ledger")
    ).data["count"] == 3


def test_customer_payments_hide_the_commission(customer_client,
                                               complete_job):
    complete_job(final_price="2000")

    resp = customer_client.get(reverse("payments:payments"))
    row = resp.data["results"][0]
    assert row["settled_amount"] == "2000.00"
    assert "commission_amount" not in row
    assert "commission_rate" not in row


def test_provider_payments_show_the_commission(provider_client,
                                               complete_job):
    complete_job(final_price="2000")

    resp = provider_client.get(reverse("payments:payments"))
    row = resp.data["results"][0]
    assert row["commission_amount"] == "240.00"
    assert row["net_amount"] == "1760.00"


def test_dashboard_summarises_the_provider(provider_client, complete_job):
    complete_job(final_price="2000")

    resp = provider_client.get(reverse("payments:dashboard"))
    assert resp.status_code == 200
    assert resp.data["earnings"]["this_month"]["gross"] == "2000.00"
    assert resp.data["earnings"]["outstanding_payable"] == "240.00"
    assert resp.data["bookings"]["upcoming"] == 0
    assert "score" in resp.data["trust"]
    assert resp.data["requests"]["open"] == 0


def test_dashboard_counts_open_requests(provider_client, customer, service,
                                        dhanmondi, provider):
    from django.utils import timezone

    from apps.bookings import services as booking_services

    start = timezone.now() + timezone.timedelta(days=2)
    booking_services.create_request(
        customer_id=customer.id, service_id=service.id,
        location_id=dhanmondi.id, address="x", description="y",
        preferred_start=start,
        preferred_end=start + timezone.timedelta(hours=2),
    )

    resp = provider_client.get(reverse("payments:dashboard"))
    assert resp.data["requests"]["open"] == 1


def test_flagged_queue_requires_admin(provider_client):
    assert provider_client.get(
        reverse("payments:flagged")
    ).status_code == 403


def test_admin_sees_and_resolves_a_flagged_payment(admin_client,
                                                   complete_job, provider):
    booking = complete_job(final_price="2500", confirmed_price="2000")

    queue = admin_client.get(reverse("payments:flagged"))
    assert queue.data["count"] == 1
    payment_id = queue.data["results"][0]["id"]

    resp = admin_client.post(
        reverse("payments:resolve", args=[payment_id]),
        {"settled_amount": "2000", "note": "Customer receipt matches."},
        format="json",
    )
    assert resp.status_code == 200
    assert resp.data["status"] == "settled"
    assert admin_client.get(reverse("payments:flagged")).data["count"] == 0
    assert LedgerEntry.objects.filter(booking=booking).count() == 3


def test_provider_cannot_resolve_their_own_flag(provider_client,
                                                complete_job):
    booking = complete_job(final_price="2500", confirmed_price="2000")
    payment = Payment.objects.get(booking=booking)

    resp = provider_client.post(
        reverse("payments:resolve", args=[payment.id]),
        {"settled_amount": "2500", "note": "Trust me"}, format="json",
    )
    assert resp.status_code == 403
    payment.refresh_from_db()
    assert payment.status == Payment.Status.FLAGGED


def test_admin_records_a_settlement(admin_client, complete_job, provider):
    complete_job(final_price="2000")

    resp = admin_client.post(
        reverse("payments:settlement", args=[provider.id]),
        {"amount": "240", "reference": "bKash TX123"}, format="json",
    )
    assert resp.status_code == 201
    assert resp.data["kind"] == "settlement"
    assert resp.data["amount"] == "240.00"


def test_oversized_settlement_uses_the_error_envelope(admin_client,
                                                      complete_job,
                                                      provider):
    complete_job(final_price="2000")

    resp = admin_client.post(
        reverse("payments:settlement", args=[provider.id]),
        {"amount": "500"}, format="json",
    )
    assert resp.status_code == 400
    assert resp.data["error"]["code"] == "settlement_exceeds_payable"
    assert resp.data["error"]["details"]["outstanding_payable"] == "240.00"


def test_provider_cannot_record_their_own_settlement(provider_client,
                                                     complete_job, provider):
    complete_job(final_price="2000")
    resp = provider_client.post(
        reverse("payments:settlement", args=[provider.id]),
        {"amount": "240"}, format="json",
    )
    assert resp.status_code == 403
    assert not LedgerEntry.objects.filter(
        kind=LedgerEntry.Kind.SETTLEMENT,
    ).exists()


def test_confirm_endpoint_creates_the_payment(customer_client,
                                              provider_client, customer,
                                              service, dhanmondi, provider,
                                              django_capture_on_commit_callbacks):
    from django.utils import timezone

    start = timezone.now() + timezone.timedelta(days=2)
    created = customer_client.post(reverse("bookings:requests"), {
        "service": service.id, "location": dhanmondi.id,
        "address": "House 12", "description": "AC not cooling",
        "preferred_start": start.isoformat(),
        "preferred_end": (start + timezone.timedelta(hours=2)).isoformat(),
    }, format="json")
    booking = provider_client.post(
        reverse("bookings:respond", args=[created.data["id"]]),
        {"accept": True}, format="json",
    )
    booking_id = booking.data["id"]
    provider_client.post(reverse("bookings:booking-start",
                                 args=[booking_id]))
    provider_client.post(reverse("bookings:booking-complete",
                                 args=[booking_id]),
                         {"final_price": "1800"}, format="json")
    with django_capture_on_commit_callbacks(execute=True):
        customer_client.post(reverse("bookings:booking-confirm",
                                     args=[booking_id]),
                             {"confirmed_price": "1800"}, format="json")

    payment = Payment.objects.get(booking_id=booking_id)
    assert payment.settled_amount == Decimal("1800.00")
    assert payment.commission_amount == Decimal("216.00")
