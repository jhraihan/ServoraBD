import pytest
from django.contrib import admin
from django.test import RequestFactory

from apps.reviews import services
from apps.reviews.models import Review

pytestmark = pytest.mark.django_db


@pytest.fixture
def review(completed_booking, customer):
    return services.create_review(booking_id=completed_booking.id,
                                  customer_id=customer.id, rating=2,
                                  comment="Rude and late.")


def _form(user, review, data):
    request = RequestFactory().post("/admin/")
    request.user = user
    model_admin = admin.site._registry[Review]
    return request, model_admin, model_admin.get_form(request, review)(
        data, instance=review,
    )


def test_admin_hiding_runs_through_the_moderation_service(
        admin_user, review, django_capture_on_commit_callbacks):
    request, model_admin, form = _form(
        admin_user, review, {"is_hidden": "on", "hidden_reason": "Abusive"},
    )
    assert form.is_valid(), form.errors

    with django_capture_on_commit_callbacks(execute=True):
        model_admin.save_model(request, model_admin.save_form(
            request, form, change=True), form, change=True)

    review.refresh_from_db()
    assert review.is_hidden is True
    assert review.hidden_by == admin_user
    assert review.hidden_at is not None


def test_admin_hiding_needs_a_reason(admin_user, review):
    _, _, form = _form(admin_user, review,
                       {"is_hidden": "on", "hidden_reason": " "})
    assert not form.is_valid()
    assert "hidden_reason" in form.errors


def test_review_content_is_read_only_in_the_admin(admin_user, review):
    request, model_admin, _ = _form(admin_user, review, {})
    readonly = model_admin.get_readonly_fields(request, review)
    assert {"rating", "comment", "customer"} <= set(readonly)
    assert "is_hidden" not in readonly
