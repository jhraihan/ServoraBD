from decimal import Decimal

import pytest
from django.utils import timezone

from apps.bookings import services
from apps.bookings.models import Booking
from apps.common.testing import (
    admin_session, assert_change_page_and_dialogs_render, post_action,
)

pytestmark = pytest.mark.django_db


def test_admin_resolves_a_dispute(customer, provider, service, dhanmondi,
                                  admin_user):
    start = timezone.now() + timezone.timedelta(days=2)
    request = services.create_request(
        customer_id=customer.id, service_id=service.id,
        location_id=dhanmondi.id, address="House 12",
        description="AC not cooling", preferred_start=start,
        preferred_end=start + timezone.timedelta(hours=3),
    )
    booking = services.respond_to_request(request_id=request.id,
                                          provider_id=provider.id,
                                          accept=True)
    services.start_job(booking_id=booking.id, provider_id=provider.id)
    services.complete_job(booking_id=booking.id, provider_id=provider.id)
    services.open_dispute(booking_id=booking.id, customer_id=customer.id,
                          reason="Left a mess.")

    client = admin_session(admin_user)
    assert_change_page_and_dialogs_render(client, booking,
                                          ["resolve_dispute"])

    post_action(client, "bookings_booking_resolve_dispute",
                booking, settled_price="1500",
                note="Partial refund for the clean-up.")

    booking.refresh_from_db()
    assert booking.state == Booking.State.COMPLETED
    assert booking.customer_confirmed_price == Decimal("1500")
