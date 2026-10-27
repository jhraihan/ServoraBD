from decimal import Decimal

import pytest
from django.utils import timezone

from apps.accounts.models import ProviderProfile
from apps.bookings import services
from apps.bookings.models import (
    Booking, BookingEvent, ProviderResponse, ServiceRequest,
)
from apps.common.exceptions import (
    DomainError, InvalidStateTransition, NotFound,
)

pytestmark = pytest.mark.django_db

State = Booking.State


def _make_request(customer, service, location, future_window,
                  target_provider_id=None):
    start, end = future_window
    return services.create_request(
        customer_id=customer.id, service_id=service.id,
        location_id=location.id, address="House 12, Road 5",
        description="AC not cooling", preferred_start=start,
        preferred_end=end, target_provider_id=target_provider_id,
    )


def _booked(customer, provider, service, location, future_window):
    request = _make_request(customer, service, location, future_window)
    return services.respond_to_request(
        request_id=request.id, provider_id=provider.id, accept=True,
    )


def test_create_request_opens_it(customer, service, dhanmondi,
                                 future_window):
    request = _make_request(customer, service, dhanmondi, future_window)
    assert request.state == ServiceRequest.State.OPEN
    assert request.kind == ServiceRequest.Kind.BROADCAST
    assert request.expires_at > timezone.now()


def test_direct_request_records_its_target(customer, provider, service,
                                           dhanmondi, future_window):
    request = _make_request(customer, service, dhanmondi, future_window,
                            target_provider_id=provider.id)
    assert request.kind == ServiceRequest.Kind.DIRECT
    assert request.target_provider_id == provider.id


def test_request_window_must_be_ordered(customer, service, dhanmondi):
    start = timezone.now() + timezone.timedelta(days=2)
    with pytest.raises(DomainError) as exc:
        services.create_request(
            customer_id=customer.id, service_id=service.id,
            location_id=dhanmondi.id, address="x", description="y",
            preferred_start=start,
            preferred_end=start - timezone.timedelta(hours=1),
        )
    assert exc.value.code == "invalid_window"


def test_request_cannot_be_in_the_past(customer, service, dhanmondi):
    past = timezone.now() - timezone.timedelta(days=1)
    with pytest.raises(DomainError) as exc:
        services.create_request(
            customer_id=customer.id, service_id=service.id,
            location_id=dhanmondi.id, address="x", description="y",
            preferred_start=past,
            preferred_end=past + timezone.timedelta(hours=2),
        )
    assert exc.value.code == "window_in_past"


def test_creating_a_request_counts_towards_responsiveness(
        customer, provider, service, dhanmondi, future_window):
    before = ProviderProfile.objects.get(pk=provider.id).requests_received
    _make_request(customer, service, dhanmondi, future_window)
    after = ProviderProfile.objects.get(pk=provider.id).requests_received
    assert after == before + 1


def test_accept_creates_a_booking_and_locks_the_price(
        customer, provider, service, dhanmondi, future_window):
    request = _make_request(customer, service, dhanmondi, future_window)
    booking = services.respond_to_request(
        request_id=request.id, provider_id=provider.id, accept=True,
    )

    assert booking.state == State.SCHEDULED
    assert booking.agreed_price == Decimal("1800")

    request.refresh_from_db()
    assert request.state == ServiceRequest.State.ACCEPTED


def test_accept_increments_jobs_accepted(customer, provider, service,
                                         dhanmondi, future_window):
    _booked(customer, provider, service, dhanmondi, future_window)
    assert ProviderProfile.objects.get(pk=provider.id).jobs_accepted == 1


def test_decline_records_a_response_without_a_booking(
        customer, provider, service, dhanmondi, future_window):
    request = _make_request(customer, service, dhanmondi, future_window)
    booking = services.respond_to_request(
        request_id=request.id, provider_id=provider.id, accept=False,
        reason="Fully booked",
    )

    assert booking is None
    assert not Booking.objects.exists()

    response = ProviderResponse.objects.get(request=request)
    assert response.decision == ProviderResponse.Decision.DECLINED
    assert response.reason == "Fully booked"

    request.refresh_from_db()
    assert request.state == ServiceRequest.State.OPEN


def test_first_acceptance_wins_on_a_broadcast(
        customer, provider, other_provider, service, dhanmondi,
        future_window):
    request = _make_request(customer, service, dhanmondi, future_window)
    services.respond_to_request(request_id=request.id,
                                provider_id=provider.id, accept=True)

    with pytest.raises(DomainError) as exc:
        services.respond_to_request(request_id=request.id,
                                    provider_id=other_provider.id,
                                    accept=True)
    assert exc.value.code == "request_closed"
    assert Booking.objects.count() == 1


def test_a_provider_cannot_respond_twice(customer, provider, service,
                                         dhanmondi, future_window):
    request = _make_request(customer, service, dhanmondi, future_window)
    services.respond_to_request(request_id=request.id,
                                provider_id=provider.id, accept=False)

    with pytest.raises(DomainError) as exc:
        services.respond_to_request(request_id=request.id,
                                    provider_id=provider.id, accept=True)
    assert exc.value.code == "already_responded"


def test_ineligible_provider_cannot_respond(customer, provider, service,
                                            dhaka, gulshan_free,
                                            future_window):
    request = _make_request(customer, service, gulshan_free, future_window)
    with pytest.raises(DomainError) as exc:
        services.respond_to_request(request_id=request.id,
                                    provider_id=provider.id, accept=True)
    assert exc.value.code == "not_eligible"


def test_response_time_feeds_the_median(customer, provider, service,
                                        dhanmondi, future_window):
    request = _make_request(customer, service, dhanmondi, future_window)
    services.respond_to_request(request_id=request.id,
                                provider_id=provider.id, accept=False)

    provider.refresh_from_db()
    assert provider.median_response_seconds is not None


def test_withdraw_closes_an_open_request(customer, service, dhanmondi,
                                         future_window):
    request = _make_request(customer, service, dhanmondi, future_window)
    withdrawn = services.withdraw_request(request_id=request.id,
                                          customer_id=customer.id)
    assert withdrawn.state == ServiceRequest.State.WITHDRAWN


def test_withdraw_rejects_an_accepted_request(customer, provider, service,
                                              dhanmondi, future_window):
    request = _make_request(customer, service, dhanmondi, future_window)
    services.respond_to_request(request_id=request.id,
                                provider_id=provider.id, accept=True)

    with pytest.raises(DomainError) as exc:
        services.withdraw_request(request_id=request.id,
                                  customer_id=customer.id)
    assert exc.value.code == "request_not_open"


def test_expiry_closes_unanswered_requests(customer, service, dhanmondi,
                                           future_window):
    request = _make_request(customer, service, dhanmondi, future_window)
    ServiceRequest.objects.filter(pk=request.id).update(
        expires_at=timezone.now() - timezone.timedelta(minutes=1),
    )

    assert services.expire_stale_requests() == 1
    request.refresh_from_db()
    assert request.state == ServiceRequest.State.EXPIRED


def test_expiry_is_not_recorded_as_a_decline(customer, provider, service,
                                             dhanmondi, future_window):
    request = _make_request(customer, service, dhanmondi, future_window)
    ServiceRequest.objects.filter(pk=request.id).update(
        expires_at=timezone.now() - timezone.timedelta(minutes=1),
    )
    services.expire_stale_requests()

    assert not ProviderResponse.objects.filter(request=request).exists()


def test_expiry_is_idempotent(customer, service, dhanmondi, future_window):
    request = _make_request(customer, service, dhanmondi, future_window)
    ServiceRequest.objects.filter(pk=request.id).update(
        expires_at=timezone.now() - timezone.timedelta(minutes=1),
    )
    assert services.expire_stale_requests() == 1
    assert services.expire_stale_requests() == 0


def test_full_happy_path(customer, provider, service, dhanmondi,
                         future_window, django_capture_on_commit_callbacks):
    booking = _booked(customer, provider, service, dhanmondi, future_window)

    booking = services.start_job(booking_id=booking.id,
                                 provider_id=provider.id)
    assert booking.state == State.IN_PROGRESS
    assert booking.started_at is not None

    booking = services.complete_job(booking_id=booking.id,
                                    provider_id=provider.id,
                                    final_price=Decimal("2000"))
    assert booking.state == State.AWAITING_CONFIRM
    assert booking.final_price == Decimal("2000")

    with django_capture_on_commit_callbacks(execute=True):
        booking = services.confirm_completion(
            booking_id=booking.id, customer_id=customer.id,
            confirmed_price=Decimal("2000"),
        )

    assert booking.state == State.COMPLETED
    assert ProviderProfile.objects.get(pk=provider.id).jobs_completed == 1


def test_completion_recomputes_trust(customer, provider, service, dhanmondi,
                                     future_window,
                                     django_capture_on_commit_callbacks):
    from apps.trust.models import TrustSnapshot

    booking = _booked(customer, provider, service, dhanmondi, future_window)
    services.start_job(booking_id=booking.id, provider_id=provider.id)
    services.complete_job(booking_id=booking.id, provider_id=provider.id)

    with django_capture_on_commit_callbacks(execute=True):
        services.confirm_completion(booking_id=booking.id,
                                    customer_id=customer.id)

    snapshot = TrustSnapshot.objects.filter(provider=provider).first()
    assert snapshot is not None
    assert snapshot.trigger == TrustSnapshot.Trigger.BOOKING_COMPLETED


def test_every_transition_writes_an_event(customer, provider, service,
                                          dhanmondi, future_window,
                                          django_capture_on_commit_callbacks):
    booking = _booked(customer, provider, service, dhanmondi, future_window)
    services.start_job(booking_id=booking.id, provider_id=provider.id)
    services.complete_job(booking_id=booking.id, provider_id=provider.id)
    with django_capture_on_commit_callbacks(execute=True):
        services.confirm_completion(booking_id=booking.id,
                                    customer_id=customer.id)

    events = list(
        BookingEvent.objects.filter(booking=booking).order_by("created_at")
    )
    assert [e.to_state for e in events] == [
        State.SCHEDULED, State.IN_PROGRESS, State.AWAITING_CONFIRM,
        State.COMPLETED,
    ]


def test_events_are_append_only(customer, provider, service, dhanmondi,
                                future_window):
    booking = _booked(customer, provider, service, dhanmondi, future_window)
    event = BookingEvent.objects.filter(booking=booking).first()

    event.reason = "tampered"
    with pytest.raises(ValueError):
        event.save()
    with pytest.raises(ValueError):
        event.delete()


def test_illegal_transition_raises_not_500(customer, provider, service,
                                           dhanmondi, future_window):
    booking = _booked(customer, provider, service, dhanmondi, future_window)

    with pytest.raises(InvalidStateTransition):
        services.confirm_completion(booking_id=booking.id,
                                    customer_id=customer.id)


def test_provider_cannot_touch_another_providers_booking(
        customer, provider, other_provider, service, dhanmondi,
        future_window):
    booking = _booked(customer, provider, service, dhanmondi, future_window)

    with pytest.raises(NotFound):
        services.start_job(booking_id=booking.id,
                           provider_id=other_provider.id)


def test_provider_cancellation_counts_against_them(
        customer, provider, service, dhanmondi, future_window,
        django_capture_on_commit_callbacks):
    booking = _booked(customer, provider, service, dhanmondi, future_window)

    with django_capture_on_commit_callbacks(execute=True):
        booking = services.cancel_booking(
            booking_id=booking.id, actor=BookingEvent.Actor.PROVIDER,
            actor_user_id=provider.user_id, reason="Van broke down",
            provider_id=provider.id,
        )

    assert booking.state == State.CANCELLED_PROVIDER
    assert ProviderProfile.objects.get(pk=provider.id).jobs_cancelled == 1


def test_customer_cancellation_does_not_count_against_provider(
        customer, provider, service, dhanmondi, future_window):
    booking = _booked(customer, provider, service, dhanmondi, future_window)

    booking = services.cancel_booking(
        booking_id=booking.id, actor=BookingEvent.Actor.CUSTOMER,
        actor_user_id=customer.user_id, reason="Plans changed",
        customer_id=customer.id,
    )

    assert booking.state == State.CANCELLED_CUSTOMER
    assert ProviderProfile.objects.get(pk=provider.id).jobs_cancelled == 0


def test_cancellation_requires_a_reason(customer, provider, service,
                                        dhanmondi, future_window):
    booking = _booked(customer, provider, service, dhanmondi, future_window)

    with pytest.raises(DomainError) as exc:
        services.cancel_booking(
            booking_id=booking.id, actor=BookingEvent.Actor.CUSTOMER,
            actor_user_id=customer.user_id, reason="",
            customer_id=customer.id,
        )
    assert exc.value.code == "reason_required"


def test_cancellation_records_notice_hours(customer, provider, service,
                                           dhanmondi, future_window):
    booking = _booked(customer, provider, service, dhanmondi, future_window)
    booking = services.cancel_booking(
        booking_id=booking.id, actor=BookingEvent.Actor.CUSTOMER,
        actor_user_id=customer.user_id, reason="Changed mind",
        customer_id=customer.id,
    )

    assert booking.notice_hours > 40
    assert booking.cancelled_at is not None


def test_auto_confirm_after_the_window(customer, provider, service,
                                       dhanmondi, future_window,
                                       django_capture_on_commit_callbacks):
    booking = _booked(customer, provider, service, dhanmondi, future_window)
    services.start_job(booking_id=booking.id, provider_id=provider.id)
    services.complete_job(booking_id=booking.id, provider_id=provider.id)

    Booking.objects.filter(pk=booking.id).update(
        completed_at=timezone.now() - timezone.timedelta(hours=80),
    )

    with django_capture_on_commit_callbacks(execute=True):
        assert services.auto_confirm_bookings() == 1

    booking.refresh_from_db()
    assert booking.state == State.COMPLETED
    assert booking.auto_confirmed is True


def test_auto_confirm_does_not_accept_a_raised_final_price(
        customer, provider, service, dhanmondi, future_window,
        django_capture_on_commit_callbacks):
    from apps.payments.models import Payment

    booking = _booked(customer, provider, service, dhanmondi, future_window)
    services.start_job(booking_id=booking.id, provider_id=provider.id)
    services.complete_job(booking_id=booking.id, provider_id=provider.id,
                          final_price=booking.agreed_price + 5000)
    Booking.objects.filter(pk=booking.id).update(
        completed_at=timezone.now() - timezone.timedelta(hours=80),
    )

    with django_capture_on_commit_callbacks(execute=True):
        assert services.auto_confirm_bookings() == 1

    booking.refresh_from_db()
    assert booking.customer_confirmed_price == booking.agreed_price
    assert Payment.objects.get(booking=booking).status ==         Payment.Status.FLAGGED

def test_auto_confirm_leaves_recent_bookings_alone(
        customer, provider, service, dhanmondi, future_window):
    booking = _booked(customer, provider, service, dhanmondi, future_window)
    services.start_job(booking_id=booking.id, provider_id=provider.id)
    services.complete_job(booking_id=booking.id, provider_id=provider.id)

    assert services.auto_confirm_bookings() == 0
    booking.refresh_from_db()
    assert booking.state == State.AWAITING_CONFIRM


def test_auto_confirm_is_idempotent(customer, provider, service, dhanmondi,
                                    future_window,
                                    django_capture_on_commit_callbacks):
    booking = _booked(customer, provider, service, dhanmondi, future_window)
    services.start_job(booking_id=booking.id, provider_id=provider.id)
    services.complete_job(booking_id=booking.id, provider_id=provider.id)
    Booking.objects.filter(pk=booking.id).update(
        completed_at=timezone.now() - timezone.timedelta(hours=80),
    )

    with django_capture_on_commit_callbacks(execute=True):
        assert services.auto_confirm_bookings() == 1
    assert services.auto_confirm_bookings() == 0


def test_price_mismatch_is_detectable(customer, provider, service, dhanmondi,
                                      future_window,
                                      django_capture_on_commit_callbacks):
    booking = _booked(customer, provider, service, dhanmondi, future_window)
    services.start_job(booking_id=booking.id, provider_id=provider.id)
    services.complete_job(booking_id=booking.id, provider_id=provider.id,
                          final_price=Decimal("2500"))

    with django_capture_on_commit_callbacks(execute=True):
        booking = services.confirm_completion(
            booking_id=booking.id, customer_id=customer.id,
            confirmed_price=Decimal("2000"),
        )

    assert booking.price_mismatch is True


def test_dispute_from_completed(customer, provider, service, dhanmondi,
                                future_window,
                                django_capture_on_commit_callbacks):
    booking = _booked(customer, provider, service, dhanmondi, future_window)
    services.start_job(booking_id=booking.id, provider_id=provider.id)
    services.complete_job(booking_id=booking.id, provider_id=provider.id)
    with django_capture_on_commit_callbacks(execute=True):
        services.confirm_completion(booking_id=booking.id,
                                    customer_id=customer.id)

    booking = services.open_dispute(booking_id=booking.id,
                                    customer_id=customer.id,
                                    reason="Fault came back")
    assert booking.state == State.DISPUTED
