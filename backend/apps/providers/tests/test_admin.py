import pytest
from django.contrib import admin
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory
from django.urls import reverse

from apps.common.testing import (
    admin_session, assert_change_page_and_dialogs_render, post_action,
)
from apps.providers import services
from apps.providers.models import VerificationDocument

pytestmark = pytest.mark.django_db

JPEG_BYTES = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00" + b"\x00" * 32


@pytest.fixture
def document(provider):
    return services.submit_verification_document(
        provider_id=provider.id, document_type="nid_front",
        file=SimpleUploadedFile("doc.jpg", JPEG_BYTES,
                                content_type="image/jpeg"),
    )


def _request(user):
    request = RequestFactory().post("/admin/")
    request.user = user
    return request


def _form(request, document, data):
    model_admin = admin.site._registry[VerificationDocument]
    return model_admin, model_admin.get_form(request, document)(
        data, instance=document,
    )


def test_admin_approval_runs_through_the_verification_service(
        admin_user, document, django_capture_on_commit_callbacks):
    request = _request(admin_user)
    model_admin, form = _form(request, document,
                              {"status": "approved", "rejection_reason": ""})
    assert form.is_valid(), form.errors

    with django_capture_on_commit_callbacks(execute=True):
        model_admin.save_model(request, model_admin.save_form(
            request, form, change=True), form, change=True)

    document.refresh_from_db()
    assert document.status == VerificationDocument.Status.APPROVED
    assert document.reviewed_by == admin_user
    assert document.purge_after is not None


def test_admin_rejection_needs_a_reason(admin_user, document):
    _, form = _form(_request(admin_user), document,
                    {"status": "rejected", "rejection_reason": ""})
    assert not form.is_valid()
    assert "rejection_reason" in form.errors


def test_a_reviewed_document_is_locked_in_the_admin(
        admin_user, document, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        services.decide_verification(document_id=document.id,
                                     reviewer_id=admin_user.id, approve=True)
    document.refresh_from_db()
    model_admin = admin.site._registry[VerificationDocument]

    readonly = model_admin.get_readonly_fields(_request(admin_user), document)
    assert {"status", "rejection_reason", "provider"} <= set(readonly)


def test_approve_action_verifies_the_document(
        admin_user, document, django_capture_on_commit_callbacks):
    client = admin_session(admin_user)
    assert_change_page_and_dialogs_render(client, document,
                                          ["approve", "reject"])

    with django_capture_on_commit_callbacks(execute=True):
        post_action(client, "providers_verificationdocument_approve",
                    document)

    document.refresh_from_db()
    assert document.status == VerificationDocument.Status.APPROVED
    assert document.reviewed_by == admin_user


def test_reject_action_records_the_reason(admin_user, document):
    post_action(admin_session(admin_user),
                "providers_verificationdocument_reject", document,
                reason="Photo is blurred; NID number unreadable.")

    document.refresh_from_db()
    assert document.status == VerificationDocument.Status.REJECTED
    assert document.rejection_reason.startswith("Photo is blurred")


def test_document_link_opens_for_a_verified_admin_session(admin_user,
                                                          document):
    resp = admin_session(admin_user).get(
        reverse("providers:verification-file", args=[document.pk]))
    assert resp.status_code == 200
    assert resp["Content-Security-Policy"] == "default-src 'none'; sandbox"
