from decimal import Decimal

import pytest
from django.contrib.messages import get_messages

from apps.common.testing import (
    admin_session, assert_change_page_and_dialogs_render, post_action,
)
from apps.payments.models import LedgerEntry, Payment

pytestmark = pytest.mark.django_db


def test_admin_settles_a_flagged_payment(admin_user, complete_job):
    booking = complete_job(final_price="2500", confirmed_price="2000")
    payment = Payment.objects.get(booking=booking)
    client = admin_session(admin_user)
    assert_change_page_and_dialogs_render(client, payment, ["resolve"])

    post_action(client, "payments_payment_resolve",
                payment, settled_amount="2000",
                note="Customer's bKash receipt shows 2000.")

    payment.refresh_from_db()
    assert payment.status == Payment.Status.SETTLED
    assert payment.settled_amount == Decimal("2000")
    assert payment.resolved_by == admin_user


def test_admin_records_a_settlement_from_the_provider_page(
        admin_user, complete_job, provider):
    complete_job(final_price="2000")
    client = admin_session(admin_user)
    assert_change_page_and_dialogs_render(
        client, provider, ["recompute_trust", "record_settlement"])

    post_action(client,
                "accounts_providerprofile_record_settlement", provider,
                amount="240", reference="bKash TX123")

    entry = LedgerEntry.objects.get(provider=provider,
                                    kind=LedgerEntry.Kind.SETTLEMENT)
    assert entry.amount == Decimal("240")
    assert entry.recorded_by == admin_user


def test_an_oversized_settlement_is_refused_with_a_message(
        admin_user, complete_job, provider):
    complete_job(final_price="2000")
    client = admin_session(admin_user)

    post_action(client, "accounts_providerprofile_record_settlement",
                provider, amount="500")

    assert not LedgerEntry.objects.filter(
        provider=provider, kind=LedgerEntry.Kind.SETTLEMENT).exists()
    page = client.get("/admin/")
    assert any("exceeds" in str(m) for m in get_messages(page.wsgi_request))


def test_finance_staff_can_record_a_settlement(complete_job, provider):
    from django.contrib.auth.models import Group

    from apps.accounts.models import User

    complete_job(final_price="2000")
    finance = User.objects.create_user(phone="+8801812345678",
                                       password="staffpass123",
                                       is_staff=True)
    finance.groups.add(Group.objects.get(name="Finance"))
    client = admin_session(finance)
    assert_change_page_and_dialogs_render(client, provider,
                                          ["record_settlement"])

    post_action(client, "accounts_providerprofile_record_settlement",
                provider, amount="100")

    assert LedgerEntry.objects.filter(
        provider=provider, kind=LedgerEntry.Kind.SETTLEMENT).exists()
