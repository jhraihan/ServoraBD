from datetime import date, time, timedelta
from decimal import Decimal

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework.test import APIClient

from apps.common.testing import verified_admin_client
from apps.providers import services
from apps.providers.models import ProviderService, ServiceArea

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
def provider_client(provider_user):
    return _auth(provider_user)


@pytest.fixture
def customer_client(customer_user):
    return _auth(customer_user)


@pytest.fixture
def admin_client(admin_user):
    return verified_admin_client(admin_user)


def test_provider_detail_is_public(anon, provider):
    resp = anon.get(reverse("providers:detail", args=[provider.id]))
    assert resp.status_code == 200
    assert resp.data["display_name"] == provider.display_name


def test_provider_detail_exposes_trust_breakdown(anon, provider):
    resp = anon.get(reverse("providers:detail", args=[provider.id]))
    for field in ["trust_score", "trust_tier", "identity_verified",
                  "phone_verified", "jobs_completed", "jobs_cancelled",
                  "median_response_seconds"]:
        assert field in resp.data


def test_unknown_provider_returns_error_envelope(anon):
    resp = anon.get(reverse("providers:detail", args=[99999]))
    assert resp.status_code == 404
    assert resp.data["error"]["code"] == "provider_not_found"


def test_my_profile_requires_authentication(anon):
    assert anon.get(reverse("providers:my-profile")).status_code == 401


def test_customer_cannot_reach_provider_endpoints(customer_client):
    assert customer_client.get(
        reverse("providers:my-profile")
    ).status_code == 403


def test_customer_cannot_create_offering(customer_client, service):
    resp = customer_client.post(reverse("providers:my-offerings"),
                                {"service": service.id, "price": "1800"},
                                format="json")
    assert resp.status_code == 403
    assert not ProviderService.objects.exists()


def test_provider_updates_own_profile(provider_client, provider):
    resp = provider_client.patch(reverse("providers:my-profile"),
                                 {"display_name": "Kamal AC Services",
                                  "experience_years": 14},
                                 format="json")
    assert resp.status_code == 200
    assert resp.data["display_name"] == "Kamal AC Services"


def test_provider_cannot_write_trust_score(provider_client, provider):
    provider_client.patch(reverse("providers:my-profile"),
                          {"trust_score": "99.00"}, format="json")
    provider.refresh_from_db()
    assert provider.trust_score == 0


def test_provider_cannot_self_verify(provider_client, provider):
    provider_client.patch(reverse("providers:my-profile"),
                          {"identity_verified": True}, format="json")
    provider.refresh_from_db()
    assert provider.identity_verified is False


def test_accepting_work_toggle_endpoint(provider_client, provider):
    resp = provider_client.post(reverse("providers:accepting-work"),
                                {"is_accepting_work": False}, format="json")
    assert resp.status_code == 200
    provider.refresh_from_db()
    assert provider.is_accepting_work is False


def test_create_and_list_offering(provider_client, service):
    create = provider_client.post(reverse("providers:my-offerings"),
                                  {"service": service.id, "price": "1800"},
                                  format="json")
    assert create.status_code == 201
    assert create.data["price_flag"] == "normal"

    listed = provider_client.get(reverse("providers:my-offerings"))
    assert len(listed.data) == 1


def test_duplicate_offering_rejected(provider_client, service):
    provider_client.post(reverse("providers:my-offerings"),
                         {"service": service.id, "price": "1800"},
                         format="json")
    resp = provider_client.post(reverse("providers:my-offerings"),
                                {"service": service.id, "price": "2000"},
                                format="json")
    assert resp.status_code == 400
    assert resp.data["error"]["code"] == "offering_exists"


def test_negative_price_rejected(provider_client, service):
    resp = provider_client.post(reverse("providers:my-offerings"),
                                {"service": service.id, "price": "-100"},
                                format="json")
    assert resp.status_code == 400


def test_provider_cannot_edit_another_providers_offering(
        provider_client, other_provider, service):
    offering = services.add_offering(provider_id=other_provider.id,
                                     service_id=service.id,
                                     price=Decimal("1800"))
    resp = provider_client.patch(
        reverse("providers:my-offering-detail", args=[offering.id]),
        {"price": "1"}, format="json",
    )
    assert resp.status_code == 404
    offering.refresh_from_db()
    assert offering.price == Decimal("1800")


def test_provider_cannot_delete_another_providers_offering(
        provider_client, other_provider, service):
    offering = services.add_offering(provider_id=other_provider.id,
                                     service_id=service.id,
                                     price=Decimal("1800"))
    resp = provider_client.delete(
        reverse("providers:my-offering-detail", args=[offering.id])
    )
    assert resp.status_code == 404
    assert ProviderService.objects.filter(pk=offering.id).exists()


def test_set_service_areas(provider_client, dhanmondi, gulshan):
    resp = provider_client.put(
        reverse("providers:my-service-areas"),
        {"location_ids": [dhanmondi.id, gulshan.id]}, format="json",
    )
    assert resp.status_code == 200
    assert len(resp.data) == 2


def test_city_level_service_area_rejected(provider_client, dhaka):
    resp = provider_client.put(reverse("providers:my-service-areas"),
                               {"location_ids": [dhaka.id]}, format="json")
    assert resp.status_code == 400
    assert resp.data["error"]["code"] == "location_too_broad"
    assert not ServiceArea.objects.exists()


def test_set_weekly_availability(provider_client):
    resp = provider_client.put(reverse("providers:my-availability"), {
        "windows": [
            {"weekday": 0, "start_time": "09:00", "end_time": "17:00"},
            {"weekday": 1, "start_time": "09:00", "end_time": "17:00"},
        ]
    }, format="json")
    assert resp.status_code == 200
    assert len(resp.data) == 2


def test_overlapping_availability_rejected(provider_client):
    resp = provider_client.put(reverse("providers:my-availability"), {
        "windows": [
            {"weekday": 0, "start_time": "09:00", "end_time": "13:00"},
            {"weekday": 0, "start_time": "12:00", "end_time": "16:00"},
        ]
    }, format="json")
    assert resp.status_code == 400
    assert resp.data["error"]["code"] == "overlapping_windows"


def test_public_availability_calendar(anon, provider_client, provider):
    provider_client.put(reverse("providers:my-availability"), {
        "windows": [
            {"weekday": d, "start_time": "09:00", "end_time": "17:00"}
            for d in range(7)
        ]
    }, format="json")

    resp = anon.get(reverse("providers:availability", args=[provider.id]),
                    {"days": 7})
    assert resp.status_code == 200
    assert len(resp.data["days"]) == 7
    assert all(len(d["windows"]) == 1 for d in resp.data["days"])


def test_leave_exception_shows_in_calendar(anon, provider_client, provider):
    provider_client.put(reverse("providers:my-availability"), {
        "windows": [
            {"weekday": d, "start_time": "09:00", "end_time": "17:00"}
            for d in range(7)
        ]
    }, format="json")

    tomorrow = date.today() + timedelta(days=1)
    provider_client.post(reverse("providers:my-availability-exception"),
                         {"date": tomorrow.isoformat(),
                          "is_available": False, "reason": "Leave"},
                         format="json")

    resp = anon.get(reverse("providers:availability", args=[provider.id]),
                    {"start": tomorrow.isoformat(), "days": 1})
    assert resp.data["days"][0]["windows"] == []


def test_invalid_calendar_date_rejected(anon, provider):
    resp = anon.get(reverse("providers:availability", args=[provider.id]),
                    {"start": "not-a-date"})
    assert resp.status_code == 400
    assert resp.data["error"]["code"] == "invalid_date"


def test_verification_upload(provider_client):
    resp = provider_client.post(
        reverse("providers:my-verification"),
        {"document_type": "nid_front", "file": _fake_file()},
        format="multipart",
    )
    assert resp.status_code == 201
    assert resp.data["status"] == "pending"


def test_oversized_document_rejected(provider_client):
    big = SimpleUploadedFile("big.jpg", b"x" * (6 * 1024 * 1024),
                             content_type="image/jpeg")
    resp = provider_client.post(
        reverse("providers:my-verification"),
        {"document_type": "nid_front", "file": big}, format="multipart",
    )
    assert resp.status_code == 400


def test_wrong_document_type_rejected(provider_client):
    bad = SimpleUploadedFile("script.exe", b"MZ",
                             content_type="application/x-msdownload")
    resp = provider_client.post(
        reverse("providers:my-verification"),
        {"document_type": "nid_front", "file": bad}, format="multipart",
    )
    assert resp.status_code == 400


def test_verification_queue_requires_admin(provider_client):
    assert provider_client.get(
        reverse("providers:verification-queue")
    ).status_code == 403


def test_admin_sees_pending_queue(admin_client, provider):
    services.submit_verification_document(
        provider_id=provider.id, document_type="nid_front",
        file=_fake_file(),
    )
    resp = admin_client.get(reverse("providers:verification-queue"))
    assert resp.status_code == 200
    assert resp.data["count"] == 1
    assert resp.data["results"][0]["provider_name"] == provider.display_name


def test_admin_can_view_the_document_being_verified(admin_client, provider):
    doc = services.submit_verification_document(
        provider_id=provider.id, document_type="nid_front",
        file=_fake_file(),
    )
    resp = admin_client.get(reverse("providers:verification-file",
                                    args=[doc.id]))
    assert resp.status_code == 200
    assert resp["Content-Type"] == "image/jpeg"
    assert b"".join(resp.streaming_content) == JPEG_BYTES


def test_document_file_is_refused_to_everyone_else(anon, provider_client,
                                                   customer_client, provider):
    doc = services.submit_verification_document(
        provider_id=provider.id, document_type="nid_front",
        file=_fake_file(),
    )
    url = reverse("providers:verification-file", args=[doc.id])
    assert anon.get(url).status_code == 401
    assert provider_client.get(url).status_code == 403
    assert customer_client.get(url).status_code == 403


def test_admin_document_page_renders(admin_user, provider, client):
    doc = services.submit_verification_document(
        provider_id=provider.id, document_type="nid_front",
        file=_fake_file(),
    )
    verified_admin_client(admin_user, client)
    resp = client.get(
        "/admin/providers/verificationdocument/%d/change/" % doc.id)
    assert resp.status_code == 200
    assert reverse("providers:verification-file",
                   args=[doc.id]).encode() in resp.content


def test_provider_cannot_approve_own_document(provider_client, provider):
    doc = services.submit_verification_document(
        provider_id=provider.id, document_type="nid_front",
        file=_fake_file(),
    )
    resp = provider_client.post(
        reverse("providers:verification-decide", args=[doc.id]),
        {"approve": True}, format="json",
    )
    assert resp.status_code == 403
    provider.refresh_from_db()
    assert provider.identity_verified is False


def test_admin_approves_document(admin_client, provider):
    doc = services.submit_verification_document(
        provider_id=provider.id, document_type="trade_certificate",
        file=_fake_file(),
    )
    resp = admin_client.post(
        reverse("providers:verification-decide", args=[doc.id]),
        {"approve": True}, format="json",
    )
    assert resp.status_code == 200
    assert resp.data["status"] == "approved"
    provider.refresh_from_db()
    assert provider.skill_verified is True


def test_admin_rejection_needs_reason(admin_client, provider):
    doc = services.submit_verification_document(
        provider_id=provider.id, document_type="nid_front",
        file=_fake_file(),
    )
    resp = admin_client.post(
        reverse("providers:verification-decide", args=[doc.id]),
        {"approve": False}, format="json",
    )
    assert resp.status_code == 400
    assert resp.data["error"]["code"] == "reason_required"


def test_verification_file_url_not_exposed_publicly(anon, provider_client,
                                                    provider):
    provider_client.post(
        reverse("providers:my-verification"),
        {"document_type": "nid_front", "file": _fake_file()},
        format="multipart",
    )
    resp = anon.get(reverse("providers:detail", args=[provider.id]))
    body = str(resp.data)
    assert "verification" not in body


def test_provider_sees_own_documents_without_file_path(provider_client):
    provider_client.post(
        reverse("providers:my-verification"),
        {"document_type": "nid_front", "file": _fake_file()},
        format="multipart",
    )
    resp = provider_client.get(reverse("providers:my-verification"))
    assert resp.status_code == 200
    assert "file" not in resp.data[0]


def _fake_file(name="doc.jpg"):
    return SimpleUploadedFile(name, JPEG_BYTES, content_type="image/jpeg")


def test_patch_offering_price_succeeds(provider_client, service):
    create = provider_client.post(reverse("providers:my-offerings"),
                                  {"service": service.id, "price": "1800"},
                                  format="json")
    offering_id = create.data["id"]

    resp = provider_client.patch(
        reverse("providers:my-offering-detail", args=[offering_id]),
        {"price": "2200"}, format="json",
    )
    assert resp.status_code == 200
    assert Decimal(resp.data["price"]) == Decimal("2200")


@pytest.mark.parametrize("price,expected_flag", [
    ("800", "low"),
    ("1800", "normal"),
    ("9000", "high"),
])
def test_patch_price_recomputes_band_flag(provider_client, service, price,
                                          expected_flag):
    create = provider_client.post(reverse("providers:my-offerings"),
                                  {"service": service.id, "price": "1800"},
                                  format="json")
    resp = provider_client.patch(
        reverse("providers:my-offering-detail", args=[create.data["id"]]),
        {"price": price}, format="json",
    )
    assert resp.status_code == 200
    assert resp.data["price_flag"] == expected_flag


def test_patch_offering_rejects_negative_price(provider_client, service):
    create = provider_client.post(reverse("providers:my-offerings"),
                                  {"service": service.id, "price": "1800"},
                                  format="json")
    resp = provider_client.patch(
        reverse("providers:my-offering-detail", args=[create.data["id"]]),
        {"price": "-5"}, format="json",
    )
    assert resp.status_code == 400


def test_patch_offering_rejects_unknown_field(provider_client, service):
    create = provider_client.post(reverse("providers:my-offerings"),
                                  {"service": service.id, "price": "1800"},
                                  format="json")
    resp = provider_client.patch(
        reverse("providers:my-offering-detail", args=[create.data["id"]]),
        {"trust_score": "99"}, format="json",
    )
    assert resp.status_code == 400


def test_patch_offering_deactivates(provider_client, service):
    create = provider_client.post(reverse("providers:my-offerings"),
                                  {"service": service.id, "price": "1800"},
                                  format="json")
    resp = provider_client.patch(
        reverse("providers:my-offering-detail", args=[create.data["id"]]),
        {"is_active": False}, format="json",
    )
    assert resp.status_code == 200
    assert resp.data["is_active"] is False


JPEG_BYTES = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00" + b"\x00" * 32
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
PDF_BYTES = b"%PDF-1.7\n" + b"\x00" * 32


@pytest.mark.parametrize("name,body,content_type", [
    ("nid.jpg", JPEG_BYTES, "image/jpeg"),
    ("nid.png", PNG_BYTES, "image/png"),
    ("cert.pdf", PDF_BYTES, "application/pdf"),
])
def test_genuine_documents_are_accepted(provider_client, name, body,
                                        content_type):
    resp = provider_client.post(
        reverse("providers:my-verification"),
        {"document_type": "nid_front",
         "file": SimpleUploadedFile(name, body, content_type=content_type)},
        format="multipart",
    )
    assert resp.status_code == 201


@pytest.mark.parametrize("name,body", [
    ("nid.jpg", b"<html><script>alert(1)</script></html>"),
    ("nid.jpg", b"MZ\x90\x00" + b"\x00" * 32),
    ("nid.png", b"<svg xmlns='http://www.w3.org/2000/svg'></svg>"),
    ("nid.pdf", JPEG_BYTES),
])
def test_disguised_files_are_rejected(provider_client, name, body):
    content_type = {"jpg": "image/jpeg", "png": "image/png",
                    "pdf": "application/pdf"}[name.rsplit(".", 1)[1]]
    resp = provider_client.post(
        reverse("providers:my-verification"),
        {"document_type": "nid_front",
         "file": SimpleUploadedFile(name, body, content_type=content_type)},
        format="multipart",
    )
    assert resp.status_code == 400
    from apps.providers.models import VerificationDocument
    assert not VerificationDocument.objects.exists()


def test_work_photo_over_5mb_is_rejected(provider_client):
    from io import BytesIO

    from PIL import Image

    buffer = BytesIO()
    Image.new("RGB", (8, 8)).save(buffer, format="PNG")
    oversized = buffer.getvalue() + b"\x00" * (6 * 1024 * 1024)

    resp = provider_client.post(
        reverse("providers:my-work-photos"),
        {"image": SimpleUploadedFile("big.png", oversized,
                                     content_type="image/png")},
        format="multipart",
    )
    assert resp.status_code == 400
    assert "image" in resp.data["error"]["details"]["fields"]
