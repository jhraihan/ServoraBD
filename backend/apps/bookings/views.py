from rest_framework import status
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.common.exceptions import NotFound
from apps.providers.permissions import IsProvider

from . import selectors, services
from .models import BookingEvent
from .permissions import IsCustomer
from .serializers import (
    BookingDetailSerializer, BookingSerializer, CompleteSerializer,
    InboxRequestSerializer,
    ConfirmSerializer, ProviderResponseSerializer, ReasonSerializer,
    RespondSerializer, ServiceRequestCreateSerializer,
    ServiceRequestSerializer,
)


def _acting_as_provider(user):
    return (
        hasattr(user, "provider_profile")
        and user.active_role == user.Role.PROVIDER
    )


class RequestListCreateView(APIView):
    permission_classes = [IsCustomer]
    throttle_scope = "service_request"

    def get_throttles(self):
        if self.request.method == "POST":
            return [ScopedRateThrottle()]
        return super().get_throttles()

    def get(self, request):
        qs = selectors.requests_for_customer(
            request.user.customer_profile.id,
            state=request.query_params.get("state"),
        )
        return Response(ServiceRequestSerializer(qs, many=True).data)

    def post(self, request):
        serializer = ServiceRequestCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        service_request = services.create_request(
            customer_id=request.user.customer_profile.id,
            service_id=data["service"],
            location_id=data["location"],
            address=data["address"],
            description=data["description"],
            preferred_start=data["preferred_start"],
            preferred_end=data["preferred_end"],
            target_provider_id=data.get("target_provider"),
        )
        return Response(ServiceRequestSerializer(service_request).data,
                        status=status.HTTP_201_CREATED)


class RequestDetailView(APIView):
    permission_classes = [IsCustomer]

    def get(self, request, request_id):
        qs = selectors.requests_for_customer(request.user.customer_profile.id)
        service_request = qs.filter(pk=request_id).first()
        if service_request is None:
            raise NotFound("No such request.", code="request_not_found")

        payload = ServiceRequestSerializer(service_request).data
        payload["responses"] = ProviderResponseSerializer(
            service_request.responses.all(), many=True,
        ).data
        return Response(payload)


class RequestWithdrawView(APIView):
    permission_classes = [IsCustomer]

    def post(self, request, request_id):
        service_request = services.withdraw_request(
            request_id=request_id,
            customer_id=request.user.customer_profile.id,
            reason=request.data.get("reason", ""),
        )
        return Response(ServiceRequestSerializer(service_request).data)


class ProviderInboxView(APIView):
    permission_classes = [IsProvider]

    def get(self, request):
        provider = request.user.provider_profile
        eligible = [
            r for r in selectors.open_requests_for_provider(provider)
            if services.can_provider_respond(r, provider.id)
        ]
        return Response(InboxRequestSerializer(eligible, many=True).data)


class RespondView(APIView):
    permission_classes = [IsProvider]

    def post(self, request, request_id):
        serializer = RespondSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        booking = services.respond_to_request(
            request_id=request_id,
            provider_id=request.user.provider_profile.id,
            accept=data["accept"],
            reason=data.get("reason", ""),
            scheduled_for=data.get("scheduled_for"),
            price=data.get("price"),
        )

        if booking is None:
            return Response({"accepted": False}, status=status.HTTP_200_OK)
        return Response(BookingSerializer(booking).data,
                        status=status.HTTP_201_CREATED)


class BookingListView(ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = BookingSerializer

    def get_queryset(self):
        user = self.request.user
        state = self.request.query_params.get("state")

        if _acting_as_provider(user):
            return selectors.bookings_for(
                provider_id=user.provider_profile.id, state=state,
            )
        if hasattr(user, "customer_profile"):
            return selectors.bookings_for(
                customer_id=user.customer_profile.id, state=state,
            )
        return selectors.bookings_for(customer_id=-1)


class BookingDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, booking_id):
        booking = _visible_booking(request, booking_id)
        return Response(BookingDetailSerializer(booking).data)


class StartJobView(APIView):
    permission_classes = [IsProvider]

    def post(self, request, booking_id):
        booking = services.start_job(
            booking_id=booking_id,
            provider_id=request.user.provider_profile.id,
        )
        return Response(BookingSerializer(booking).data)


class CompleteJobView(APIView):
    permission_classes = [IsProvider]

    def post(self, request, booking_id):
        serializer = CompleteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        booking = services.complete_job(
            booking_id=booking_id,
            provider_id=request.user.provider_profile.id,
            final_price=serializer.validated_data.get("final_price"),
        )
        return Response(BookingSerializer(booking).data)


class ConfirmBookingView(APIView):
    permission_classes = [IsCustomer]

    def post(self, request, booking_id):
        serializer = ConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        booking = services.confirm_completion(
            booking_id=booking_id,
            customer_id=request.user.customer_profile.id,
            confirmed_price=serializer.validated_data.get("confirmed_price"),
        )
        return Response(BookingSerializer(booking).data)


class CancelBookingView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, booking_id):
        serializer = ReasonSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reason = serializer.validated_data["reason"]
        user = request.user

        if _acting_as_provider(user):
            booking = services.cancel_booking(
                booking_id=booking_id,
                actor=BookingEvent.Actor.PROVIDER,
                actor_user_id=user.id,
                reason=reason,
                provider_id=user.provider_profile.id,
            )
        elif hasattr(user, "customer_profile"):
            booking = services.cancel_booking(
                booking_id=booking_id,
                actor=BookingEvent.Actor.CUSTOMER,
                actor_user_id=user.id,
                reason=reason,
                customer_id=user.customer_profile.id,
            )
        else:
            raise NotFound("No such booking.", code="booking_not_found")

        return Response(BookingSerializer(booking).data)


class DisputeBookingView(APIView):
    permission_classes = [IsCustomer]

    def post(self, request, booking_id):
        serializer = ReasonSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        booking = services.open_dispute(
            booking_id=booking_id,
            customer_id=request.user.customer_profile.id,
            reason=serializer.validated_data["reason"],
        )
        return Response(BookingSerializer(booking).data)


def _visible_booking(request, booking_id):
    user = request.user
    booking = None

    if hasattr(user, "customer_profile"):
        booking = selectors.booking_detail(
            booking_id, customer_id=user.customer_profile.id,
        )
    if booking is None and hasattr(user, "provider_profile"):
        booking = selectors.booking_detail(
            booking_id, provider_id=user.provider_profile.id,
        )
    if booking is None:
        raise NotFound("No such booking.", code="booking_not_found")
    return booking
