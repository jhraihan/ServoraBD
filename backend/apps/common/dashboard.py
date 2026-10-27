from datetime import timedelta

from django.contrib.auth import get_user_model
from django.urls import reverse, reverse_lazy
from django.utils import timezone

from apps.accounts.models import ProviderProfile
from apps.bookings.models import Booking
from apps.operations.models import JobRun
from apps.operations.selectors import job_health
from apps.payments.models import Payment
from apps.providers.models import VerificationDocument

User = get_user_model()

RECENT_DAYS = 7
QUEUE_PREVIEW = 5


def _can_view(model):
    meta = model._meta
    return lambda request: request.user.has_perm(
        "%s.view_%s" % (meta.app_label, meta.model_name))


def _changelist(model, query=""):
    meta = model._meta
    url = reverse("admin:%s_%s_changelist" % (meta.app_label, meta.model_name))
    return "%s?%s" % (url, query) if query else url


def _item(title, icon, model_path, badge=None):
    app_label, model_name = model_path.split(".")
    item = {
        "title": title,
        "icon": icon,
        "link": reverse_lazy("admin:%s_%s_changelist" % (app_label,
                                                          model_name)),
        "permission": lambda request: request.user.has_perm(
            "%s.view_%s" % (app_label, model_name)),
    }
    if badge:
        item["badge"] = "apps.common.dashboard.%s" % badge
    return item


def pending_verifications_badge(request):
    return VerificationDocument.objects.filter(
        status=VerificationDocument.Status.PENDING).count() or None


def open_disputes_badge(request):
    return Booking.objects.filter(state=Booking.State.DISPUTED).count() or None


def flagged_payments_badge(request):
    return Payment.objects.filter(
        status=Payment.Status.FLAGGED).count() or None


def sidebar_navigation(request):
    return [
        {
            "title": "Overview",
            "items": [
                {"title": "Dashboard", "icon": "dashboard",
                 "link": reverse_lazy("admin:index")},
                _item("Admin activity", "history", "admin.logentry"),
            ],
        },
        {
            "title": "People",
            "collapsible": True,
            "items": [
                _item("Users", "person", "accounts.user"),
                _item("Customers", "group", "accounts.customerprofile"),
                _item("Providers", "engineering", "accounts.providerprofile"),
                _item("Staff roles", "badge", "auth.group"),
                _item("Two-factor devices", "phonelink_lock",
                      "otp_totp.totpdevice"),
            ],
        },
        {
            "title": "Trust & safety",
            "collapsible": True,
            "items": [
                _item("Verification documents", "verified_user",
                      "providers.verificationdocument",
                      badge="pending_verifications_badge"),
                _item("Reviews", "reviews", "reviews.review"),
                _item("Provider replies", "reply", "reviews.providerreply"),
                _item("Customer ratings", "star", "reviews.customerrating"),
                _item("Trust snapshots", "monitoring", "trust.trustsnapshot"),
            ],
        },
        {
            "title": "Bookings",
            "collapsible": True,
            "items": [
                _item("Bookings", "event_available", "bookings.booking",
                      badge="open_disputes_badge"),
                _item("Service requests", "assignment",
                      "bookings.servicerequest"),
                _item("Provider responses", "forum",
                      "bookings.providerresponse"),
                _item("Booking events", "timeline", "bookings.bookingevent"),
            ],
        },
        {
            "title": "Money",
            "collapsible": True,
            "items": [
                _item("Payments", "payments", "payments.payment",
                      badge="flagged_payments_badge"),
                _item("Ledger", "account_balance", "payments.ledgerentry"),
            ],
        },
        {
            "title": "Catalogue",
            "collapsible": True,
            "items": [
                _item("Categories", "category", "catalogue.servicecategory"),
                _item("Services", "home_repair_service", "catalogue.service"),
                _item("Locations", "location_on", "catalogue.location"),
            ],
        },
        {
            "title": "Provider setup",
            "collapsible": True,
            "items": [
                _item("Offerings", "sell", "providers.providerservice"),
                _item("Service areas", "map", "providers.servicearea"),
                _item("Weekly availability", "schedule",
                      "providers.availability"),
                _item("Availability exceptions", "event_busy",
                      "providers.availabilityexception"),
                _item("Work photos", "photo_library", "providers.workphoto"),
            ],
        },
        {
            "title": "Operations",
            "collapsible": True,
            "items": [
                _item("Scheduled jobs", "update", "operations.jobrun"),
                _item("Phone codes", "sms", "accounts.phoneotp"),
            ],
        },
    ]


def _kpi(request, model, title, value, query="", footer=""):
    if not _can_view(model)(request):
        return None
    return {"title": title, "value": value,
            "link": _changelist(model, query), "footer": footer}


def dashboard_callback(request, context):
    since = timezone.now() - timedelta(days=RECENT_DAYS)
    jobs = job_health()
    unhealthy_jobs = [row["job"] for row in jobs if not row["healthy"]]

    kpis = [
        _kpi(request, VerificationDocument, "Verifications waiting",
             VerificationDocument.objects.filter(
                 status=VerificationDocument.Status.PENDING).count(),
             "status__exact=pending"),
        _kpi(request, Booking, "Open disputes",
             Booking.objects.filter(state=Booking.State.DISPUTED).count(),
             "state__exact=disputed"),
        _kpi(request, Payment, "Flagged payments",
             Payment.objects.filter(status=Payment.Status.FLAGGED).count(),
             "status__exact=flagged"),
        _kpi(request, JobRun, "Scheduled jobs needing attention",
             len(unhealthy_jobs), footer=", ".join(unhealthy_jobs)),
        _kpi(request, Booking, "Bookings, last %d days" % RECENT_DAYS,
             Booking.objects.filter(created_at__gte=since).count()),
        _kpi(request, User, "New users, last %d days" % RECENT_DAYS,
             User.objects.filter(date_joined__gte=since).count()),
        _kpi(request, ProviderProfile, "Providers taking work",
             ProviderProfile.objects.filter(
                 is_accepting_work=True, user__is_active=True,
                 user__suspended_at__isnull=True).count(),
             "is_accepting_work__exact=1"),
        _kpi(request, User, "Suspended accounts",
             User.objects.filter(suspended_at__isnull=False).count(),
             "suspended=yes"),
    ]

    queues = []
    if _can_view(VerificationDocument)(request):
        pending = (VerificationDocument.objects
                   .filter(status=VerificationDocument.Status.PENDING)
                   .select_related("provider").order_by("created_at")
                   [:QUEUE_PREVIEW])
        queues.append({
            "title": "Oldest verifications waiting",
            "headers": ["Provider", "Document", "Submitted"],
            "rows": [[doc.provider.display_name,
                      doc.get_document_type_display(),
                      timezone.localtime(doc.created_at)
                      .strftime("%d %b %Y, %H:%M")] for doc in pending],
            "link": _changelist(VerificationDocument,
                                "status__exact=pending"),
        })
    if _can_view(Booking)(request):
        disputes = (Booking.objects.filter(state=Booking.State.DISPUTED)
                    .select_related("provider").order_by("updated_at")
                    [:QUEUE_PREVIEW])
        queues.append({
            "title": "Oldest open disputes",
            "headers": ["Booking", "Provider", "Agreed", "Claimed"],
            "rows": [["#%s" % b.pk, b.provider.display_name,
                      b.agreed_price, b.final_price or "-"]
                     for b in disputes],
            "link": _changelist(Booking, "state__exact=disputed"),
        })

    context.update({
        "kpis": [kpi for kpi in kpis if kpi],
        "queues": queues,
    })
    return context
