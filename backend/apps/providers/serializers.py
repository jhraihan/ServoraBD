from decimal import Decimal

from rest_framework import serializers

from apps.accounts.models import ProviderProfile
from apps.catalogue.serializers import LocationSerializer, ServiceSerializer

from .models import (
    Availability, AvailabilityException, ProviderService, ServiceArea,
    VerificationDocument, WorkPhoto,
)


class ProviderServiceSerializer(serializers.ModelSerializer):
    service_detail = ServiceSerializer(source="service", read_only=True)
    price_flag = serializers.CharField(read_only=True)

    class Meta:
        model = ProviderService
        fields = ["id", "service", "service_detail", "price", "price_flag",
                  "estimated_duration_minutes", "notes", "is_active"]
        read_only_fields = ["id", "service_detail", "price_flag"]


class ProviderServiceWriteSerializer(serializers.Serializer):
    service = serializers.IntegerField()
    price = serializers.DecimalField(max_digits=10, decimal_places=2,
                                     min_value=Decimal("0"))
    estimated_duration_minutes = serializers.IntegerField(required=False,
                                                          allow_null=True,
                                                          min_value=1)
    notes = serializers.CharField(required=False, allow_blank=True,
                                  default="")


class ProviderServiceUpdateSerializer(serializers.Serializer):
    price = serializers.DecimalField(max_digits=10, decimal_places=2,
                                     min_value=Decimal("0"), required=False)
    estimated_duration_minutes = serializers.IntegerField(required=False,
                                                          allow_null=True,
                                                          min_value=1)
    notes = serializers.CharField(required=False, allow_blank=True)
    is_active = serializers.BooleanField(required=False)

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError(
                "Provide at least one field to update."
            )
        return attrs


class ServiceAreaSerializer(serializers.ModelSerializer):
    location_detail = LocationSerializer(source="location", read_only=True)

    class Meta:
        model = ServiceArea
        fields = ["id", "location", "location_detail", "travel_surcharge"]
        read_only_fields = ["id", "location_detail"]


class ServiceAreaWriteSerializer(serializers.Serializer):
    location_ids = serializers.ListField(
        child=serializers.IntegerField(), allow_empty=True,
    )
    surcharges = serializers.DictField(
        child=serializers.DecimalField(max_digits=10, decimal_places=2,
                                       min_value=Decimal("0")),
        required=False, default=dict,
    )


class AvailabilitySerializer(serializers.ModelSerializer):
    weekday_name = serializers.CharField(source="get_weekday_display",
                                         read_only=True)

    class Meta:
        model = Availability
        fields = ["id", "weekday", "weekday_name", "start_time", "end_time"]
        read_only_fields = ["id", "weekday_name"]


class AvailabilityWindowSerializer(serializers.Serializer):
    weekday = serializers.IntegerField(min_value=0, max_value=6)
    start_time = serializers.TimeField()
    end_time = serializers.TimeField()


class WeeklyAvailabilityWriteSerializer(serializers.Serializer):
    windows = AvailabilityWindowSerializer(many=True)


class AvailabilityExceptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = AvailabilityException
        fields = ["id", "date", "is_available", "start_time", "end_time",
                  "reason"]
        read_only_fields = ["id"]


class VerificationDocumentSerializer(serializers.ModelSerializer):
    document_type_display = serializers.CharField(
        source="get_document_type_display", read_only=True,
    )

    class Meta:
        model = VerificationDocument
        fields = ["id", "document_type", "document_type_display", "status",
                  "rejection_reason", "created_at", "reviewed_at"]
        read_only_fields = ["id", "status", "rejection_reason", "created_at",
                            "reviewed_at", "document_type_display"]


class VerificationUploadSerializer(serializers.Serializer):
    document_type = serializers.ChoiceField(
        choices=VerificationDocument.DocumentType.choices,
    )
    file = serializers.FileField()

    MAX_BYTES = 5 * 1024 * 1024
    FORMATS = (
        ({"jpg", "jpeg"}, b"\xff\xd8\xff"),
        ({"png"}, b"\x89PNG\r\n\x1a\n"),
        ({"pdf"}, b"%PDF-"),
    )

    def validate_file(self, value):
        if value.size > self.MAX_BYTES:
            raise serializers.ValidationError(
                "File must be 5 MB or smaller."
            )

        extension = value.name.rsplit(".", 1)[-1].lower() \
            if "." in value.name else ""
        head = value.read(16)
        value.seek(0)

        for extensions, signature in self.FORMATS:
            if extension in extensions and head.startswith(signature):
                return value

        raise serializers.ValidationError(
            "Upload a genuine JPEG, PNG or PDF. The file's contents do not "
            "match its type."
        )


class VerificationDecisionSerializer(serializers.Serializer):
    approve = serializers.BooleanField()
    rejection_reason = serializers.CharField(required=False, allow_blank=True,
                                             default="")


class VerificationQueueSerializer(VerificationDocumentSerializer):
    provider_id = serializers.IntegerField(read_only=True)
    provider_name = serializers.CharField(source="provider.display_name",
                                          read_only=True)

    class Meta(VerificationDocumentSerializer.Meta):
        fields = VerificationDocumentSerializer.Meta.fields + [
            "provider_id", "provider_name",
        ]


class WorkPhotoSerializer(serializers.ModelSerializer):
    MAX_BYTES = 5 * 1024 * 1024

    class Meta:
        model = WorkPhoto
        fields = ["id", "image", "caption", "display_order"]
        read_only_fields = ["id", "display_order"]

    def validate_image(self, value):
        if value.size > self.MAX_BYTES:
            raise serializers.ValidationError(
                "Photo must be 5 MB or smaller."
            )
        return value


class ProviderProfileWriteSerializer(serializers.Serializer):
    display_name = serializers.CharField(max_length=120, required=False)
    bio = serializers.CharField(required=False, allow_blank=True)
    experience_years = serializers.IntegerField(required=False, min_value=0,
                                                max_value=70)
    is_accepting_work = serializers.BooleanField(required=False)


class ProviderPublicSerializer(serializers.ModelSerializer):
    offerings = ProviderServiceSerializer(many=True, read_only=True)
    service_areas = ServiceAreaSerializer(many=True, read_only=True)
    availability = AvailabilitySerializer(many=True, read_only=True)
    work_photos = WorkPhotoSerializer(many=True, read_only=True)
    phone_verified = serializers.BooleanField(read_only=True)

    class Meta:
        model = ProviderProfile
        fields = [
            "id", "display_name", "bio", "experience_years",
            "is_accepting_work",
            "identity_verified", "skill_verified", "address_verified",
            "phone_verified",
            "trust_score", "trust_tier", "trust_computed_at",
            "jobs_completed", "jobs_cancelled", "jobs_accepted",
            "median_response_seconds",
            "offerings", "service_areas", "availability", "work_photos",
            "created_at",
        ]
        read_only_fields = fields


class AcceptingWorkSerializer(serializers.Serializer):
    is_accepting_work = serializers.BooleanField()


class ProviderSearchResultSerializer(serializers.ModelSerializer):
    phone_verified = serializers.BooleanField(read_only=True)
    from_price = serializers.SerializerMethodField()
    service_areas = ServiceAreaSerializer(many=True, read_only=True)

    class Meta:
        model = ProviderProfile
        fields = [
            "id", "display_name", "experience_years",
            "identity_verified", "skill_verified", "phone_verified",
            "trust_score", "trust_tier",
            "jobs_completed", "jobs_cancelled", "median_response_seconds",
            "from_price", "service_areas",
        ]
        read_only_fields = fields

    def get_from_price(self, obj):
        price = getattr(obj, "matched_price", None)
        return str(price) if price is not None else None
