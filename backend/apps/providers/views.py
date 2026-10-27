from datetime import date as date_cls
from datetime import datetime
from decimal import Decimal, InvalidOperation

from django.http import FileResponse
from rest_framework import status
from rest_framework.generics import ListAPIView
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.common.exceptions import NotFound

from . import search, selectors, services
from .permissions import ADMIN_AUTHENTICATION, IsAdminUser, IsProvider
from .serializers import (
    AcceptingWorkSerializer, AvailabilityExceptionSerializer,
    AvailabilitySerializer, ProviderProfileWriteSerializer,
    ProviderPublicSerializer, ProviderSearchResultSerializer,
    ProviderServiceSerializer,
    ProviderServiceUpdateSerializer, ProviderServiceWriteSerializer,
    ServiceAreaSerializer,
    ServiceAreaWriteSerializer, VerificationDecisionSerializer,
    VerificationDocumentSerializer, VerificationQueueSerializer,
    VerificationUploadSerializer, WeeklyAvailabilityWriteSerializer,
    WorkPhotoSerializer,
)


class ProviderDetailView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, provider_id):
        provider = selectors.provider_detail(provider_id)
        if provider is None:
            raise NotFound("No such provider.", code="provider_not_found")
        return Response(ProviderPublicSerializer(provider).data)


class ProviderAvailabilityView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, provider_id):
        start_raw = request.query_params.get("start")
        try:
            start = (
                datetime.strptime(start_raw, "%Y-%m-%d").date()
                if start_raw else date_cls.today()
            )
        except ValueError:
            return Response(
                {"error": {"code": "invalid_date",
                           "message": "start must be YYYY-MM-DD.",
                           "details": {}}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            days = min(int(request.query_params.get("days", 14)), 60)
        except ValueError:
            days = 14

        calendar = services.availability_calendar(
            provider_id=provider_id, start_date=start, days=days,
        )
        return Response({
            "provider": provider_id,
            "days": [
                {
                    "date": day.isoformat(),
                    "windows": [
                        {"start_time": s.isoformat(), "end_time": e.isoformat()}
                        for s, e in windows
                    ],
                }
                for day, windows in sorted(calendar.items())
            ],
        })


class MyProfileView(APIView):
    permission_classes = [IsProvider]

    def get(self, request):
        provider = selectors.provider_detail(request.user.provider_profile.id)
        return Response(ProviderPublicSerializer(provider).data)

    def patch(self, request):
        serializer = ProviderProfileWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        provider = services.update_profile(
            provider_id=request.user.provider_profile.id,
            **serializer.validated_data,
        )
        refreshed = selectors.provider_detail(provider.id)
        return Response(ProviderPublicSerializer(refreshed).data)


class AcceptingWorkView(APIView):
    permission_classes = [IsProvider]

    def post(self, request):
        serializer = AcceptingWorkSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        provider = services.set_accepting_work(
            provider_id=request.user.provider_profile.id,
            accepting=serializer.validated_data["is_accepting_work"],
        )
        return Response({"is_accepting_work": provider.is_accepting_work})


class MyOfferingsView(APIView):
    permission_classes = [IsProvider]

    def get(self, request):
        offerings = selectors.offerings_for(request.user.provider_profile.id)
        return Response(ProviderServiceSerializer(offerings, many=True).data)

    def post(self, request):
        serializer = ProviderServiceWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        offering = services.add_offering(
            provider_id=request.user.provider_profile.id,
            service_id=data["service"],
            price=data["price"],
            duration_minutes=data.get("estimated_duration_minutes"),
            notes=data.get("notes", ""),
        )
        return Response(ProviderServiceSerializer(offering).data,
                        status=status.HTTP_201_CREATED)


class MyOfferingDetailView(APIView):
    permission_classes = [IsProvider]

    def patch(self, request, offering_id):
        serializer = ProviderServiceUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        offering = services.update_offering(
            provider_id=request.user.provider_profile.id,
            offering_id=offering_id,
            **serializer.validated_data,
        )
        return Response(ProviderServiceSerializer(offering).data)

    def delete(self, request, offering_id):
        services.remove_offering(
            provider_id=request.user.provider_profile.id,
            offering_id=offering_id,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class MyServiceAreasView(APIView):
    permission_classes = [IsProvider]

    def get(self, request):
        areas = selectors.service_areas_for(request.user.provider_profile.id)
        return Response(ServiceAreaSerializer(areas, many=True).data)

    def put(self, request):
        serializer = ServiceAreaWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        services.set_service_areas(
            provider_id=request.user.provider_profile.id,
            location_ids=serializer.validated_data["location_ids"],
            surcharges=serializer.validated_data.get("surcharges", {}),
        )
        areas = selectors.service_areas_for(request.user.provider_profile.id)
        return Response(ServiceAreaSerializer(areas, many=True).data)


class MyAvailabilityView(APIView):
    permission_classes = [IsProvider]

    def get(self, request):
        windows = selectors.weekly_availability_for(
            request.user.provider_profile.id
        )
        return Response(AvailabilitySerializer(windows, many=True).data)

    def put(self, request):
        serializer = WeeklyAvailabilityWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        services.set_weekly_availability(
            provider_id=request.user.provider_profile.id,
            windows=serializer.validated_data["windows"],
        )
        windows = selectors.weekly_availability_for(
            request.user.provider_profile.id
        )
        return Response(AvailabilitySerializer(windows, many=True).data)


class MyAvailabilityExceptionView(APIView):
    permission_classes = [IsProvider]

    def post(self, request):
        serializer = AvailabilityExceptionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        exception = services.set_availability_exception(
            provider_id=request.user.provider_profile.id,
            date=data["date"],
            is_available=data.get("is_available", False),
            start_time=data.get("start_time"),
            end_time=data.get("end_time"),
            reason=data.get("reason", ""),
        )
        return Response(AvailabilityExceptionSerializer(exception).data,
                        status=status.HTTP_201_CREATED)


class MyVerificationView(APIView):
    permission_classes = [IsProvider]
    parser_classes = [MultiPartParser, FormParser]

    def get(self, request):
        documents = selectors.verification_documents_for(
            request.user.provider_profile.id
        )
        return Response(
            VerificationDocumentSerializer(documents, many=True).data
        )

    def post(self, request):
        serializer = VerificationUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        document = services.submit_verification_document(
            provider_id=request.user.provider_profile.id,
            document_type=serializer.validated_data["document_type"],
            file=serializer.validated_data["file"],
        )
        return Response(VerificationDocumentSerializer(document).data,
                        status=status.HTTP_201_CREATED)


class MyWorkPhotosView(APIView):
    permission_classes = [IsProvider]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        serializer = WorkPhotoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        photo = services.add_work_photo(
            provider_id=request.user.provider_profile.id,
            image=serializer.validated_data["image"],
            caption=serializer.validated_data.get("caption", ""),
        )
        return Response(WorkPhotoSerializer(photo).data,
                        status=status.HTTP_201_CREATED)


class MyWorkPhotoDetailView(APIView):
    permission_classes = [IsProvider]

    def delete(self, request, photo_id):
        services.remove_work_photo(
            provider_id=request.user.provider_profile.id,
            photo_id=photo_id,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class VerificationQueueView(ListAPIView):
    permission_classes = [IsAdminUser]
    authentication_classes = ADMIN_AUTHENTICATION
    serializer_class = VerificationQueueSerializer

    def get_queryset(self):
        return selectors.pending_verification_queue()


class VerificationFileView(APIView):
    permission_classes = [IsAdminUser]
    authentication_classes = ADMIN_AUTHENTICATION

    def get(self, request, document_id):
        document = selectors.verification_document(document_id)
        if document is None or not document.file:
            raise NotFound("Verification document not found.")

        response = FileResponse(document.file.open("rb"),
                                content_type=document.content_type)
        response["Content-Disposition"] = 'inline; filename="%s"' % (
            document.file_basename,
        )
        response["Cache-Control"] = "no-store"
        response["X-Content-Type-Options"] = "nosniff"
        response["Content-Security-Policy"] = "default-src 'none'; sandbox"
        return response


class VerificationDecisionView(APIView):
    permission_classes = [IsAdminUser]
    authentication_classes = ADMIN_AUTHENTICATION

    def post(self, request, document_id):
        serializer = VerificationDecisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        document = services.decide_verification(
            document_id=document_id,
            reviewer_id=request.user.id,
            approve=serializer.validated_data["approve"],
            rejection_reason=serializer.validated_data.get(
                "rejection_reason", ""
            ),
        )
        return Response(VerificationDocumentSerializer(document).data)


class ProviderSearchView(ListAPIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "search"
    serializer_class = ProviderSearchResultSerializer

    def get_queryset(self):
        params = self.request.query_params
        return search.search_providers(
            service_id=_as_int(params.get("service")),
            category_slug=params.get("category"),
            location_id=_as_int(params.get("location")),
            min_trust=_as_decimal(params.get("min_trust")),
            tier=params.get("tier"),
            verified_only=params.get("verified_only") in ("1", "true", "True"),
            price_min=_as_decimal(params.get("price_min")),
            price_max=_as_decimal(params.get("price_max")),
            available_on=_as_date(params.get("available_on")),
            ordering=params.get("ordering", search.SORT_TRUST),
        )


def _as_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_decimal(value):
    try:
        return Decimal(value)
    except (TypeError, InvalidOperation):
        return None


def _as_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None
