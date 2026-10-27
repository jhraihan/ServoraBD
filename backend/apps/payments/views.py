from datetime import datetime

from django.utils import timezone
from rest_framework import status
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.bookings import selectors as booking_selectors
from apps.bookings import services as booking_services
from apps.bookings.models import Booking
from apps.bookings.serializers import BookingSerializer
from apps.providers.permissions import (
    ADMIN_AUTHENTICATION, IsAdminUser, IsProvider,
)

from . import selectors, services
from .serializers import (
    AdminPaymentSerializer, CustomerPaymentSerializer,
    EarningsPeriodSerializer, EarningsSummarySerializer,
    EarningsTotalsSerializer, LedgerEntrySerializer,
    ProviderPaymentSerializer, ResolvePaymentSerializer,
    SettlementSerializer,
)

UPCOMING_PREVIEW = 5


def _parse_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def _acting_as_provider(user):
    return (
        hasattr(user, "provider_profile")
        and user.active_role == user.Role.PROVIDER
    )


class PaymentListView(ListAPIView):
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if _acting_as_provider(self.request.user):
            return ProviderPaymentSerializer
        return CustomerPaymentSerializer

    def get_queryset(self):
        user = self.request.user
        if _acting_as_provider(user):
            return selectors.payments_for(
                provider_id=user.provider_profile.id,
            )
        if hasattr(user, "customer_profile"):
            return selectors.payments_for(
                customer_id=user.customer_profile.id,
            )
        return selectors.payments_for(customer_id=-1)


class ProviderEarningsView(APIView):
    permission_classes = [IsProvider]

    def get(self, request):
        provider_id = request.user.provider_profile.id
        params = request.query_params
        start = _parse_date(params.get("start"))
        end = _parse_date(params.get("end"))
        period = params.get("period", "month")
        if period not in selectors.PERIOD_FUNCTIONS:
            period = "month"

        summary = selectors.earnings_summary(provider_id, start=start,
                                             end=end)
        periods = selectors.earnings_by_period(provider_id, period=period,
                                               start=start, end=end)
        return Response({
            "currency": "BDT",
            "period": period,
            "start": start.isoformat() if start else None,
            "end": end.isoformat() if end else None,
            "summary": EarningsSummarySerializer(summary).data,
            "periods": EarningsPeriodSerializer(periods, many=True).data,
        })


class ProviderLedgerView(ListAPIView):
    permission_classes = [IsProvider]
    serializer_class = LedgerEntrySerializer

    def get_queryset(self):
        return selectors.ledger_for(
            self.request.user.provider_profile.id,
            kind=self.request.query_params.get("kind"),
        )


class ProviderDashboardView(APIView):
    permission_classes = [IsProvider]

    def get(self, request):
        provider = request.user.provider_profile
        now = timezone.now()
        month_start = now.date().replace(day=1)

        bookings = booking_selectors.bookings_for(provider_id=provider.id)
        upcoming = (
            bookings
            .filter(state=Booking.State.SCHEDULED, scheduled_for__gte=now)
            .order_by("scheduled_for")
        )
        inbox = [
            r for r in booking_selectors.open_requests_for_provider(provider)
            if booking_services.can_provider_respond(r, provider.id)
        ]

        return Response({
            "trust": {
                "score": str(provider.trust_score),
                "tier": provider.trust_tier,
                "computed_at": provider.trust_computed_at,
            },
            "requests": {"open": len(inbox)},
            "bookings": {
                "upcoming": upcoming.count(),
                "in_progress": bookings.filter(
                    state=Booking.State.IN_PROGRESS).count(),
                "awaiting_confirm": bookings.filter(
                    state=Booking.State.AWAITING_CONFIRM).count(),
                "next": BookingSerializer(
                    upcoming[:UPCOMING_PREVIEW], many=True,
                ).data,
            },
            "earnings": {
                "this_month": EarningsTotalsSerializer(
                    selectors.earnings_summary(provider.id,
                                               start=month_start),
                ).data,
                "outstanding_payable": str(
                    services.outstanding_payable(provider.id)
                ),
            },
            "is_accepting_work": provider.is_accepting_work,
        })


class FlaggedPaymentListView(ListAPIView):
    permission_classes = [IsAdminUser]
    authentication_classes = ADMIN_AUTHENTICATION
    serializer_class = AdminPaymentSerializer

    def get_queryset(self):
        return selectors.flagged_payments()


class ResolvePaymentView(APIView):
    permission_classes = [IsAdminUser]
    authentication_classes = ADMIN_AUTHENTICATION

    def post(self, request, payment_id):
        serializer = ResolvePaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        payment = services.resolve_flagged_payment(
            payment_id=payment_id,
            admin_user_id=request.user.id,
            settled_amount=serializer.validated_data["settled_amount"],
            note=serializer.validated_data["note"],
        )
        return Response(AdminPaymentSerializer(payment).data)


class ProviderSettlementView(APIView):
    permission_classes = [IsAdminUser]
    authentication_classes = ADMIN_AUTHENTICATION

    def post(self, request, provider_id):
        serializer = SettlementSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        entry = services.record_provider_settlement(
            provider_id=provider_id,
            amount=serializer.validated_data["amount"],
            admin_user_id=request.user.id,
            reference=serializer.validated_data.get("reference", ""),
        )
        return Response(LedgerEntrySerializer(entry).data,
                        status=status.HTTP_201_CREATED)
