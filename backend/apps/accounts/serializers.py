from django.contrib.auth import get_user_model
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.serializers import (
    TokenObtainPairSerializer, TokenRefreshSerializer,
)
from rest_framework_simplejwt.settings import api_settings

from .models import CustomerProfile, PhoneOTP, ProviderProfile
from .validators import normalise_bd_phone, validate_bd_phone

User = get_user_model()

class PhoneField(serializers.CharField):
    def to_internal_value(self, data):
        value = normalise_bd_phone(super().to_internal_value(data))
        validate_bd_phone(value)
        return value

class CustomerProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerProfile
        fields = ["id", "default_address", "created_at"]
        read_only_fields = ["id", "created_at"]

class ProviderProfileSerializer(serializers.ModelSerializer):
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
            "created_at",
        ]
        read_only_fields = [
            "id", "created_at",
            "identity_verified", "skill_verified", "address_verified",
            "phone_verified",
            "trust_score", "trust_tier", "trust_computed_at",
            "jobs_completed", "jobs_cancelled", "jobs_accepted",
            "median_response_seconds",
        ]

class UserSerializer(serializers.ModelSerializer):
    roles = serializers.SerializerMethodField()
    customer_profile = CustomerProfileSerializer(read_only=True)
    provider_profile = ProviderProfileSerializer(read_only=True)

    class Meta:
        model = User
        fields = [
            "id", "phone", "email", "full_name",
            "phone_verified", "email_verified",
            "active_role", "roles",
            "customer_profile", "provider_profile",
            "date_joined",
        ]
        read_only_fields = [
            "id", "phone", "email", "phone_verified", "email_verified",
            "active_role", "roles", "date_joined",
        ]

    def get_roles(self, obj):
        return obj.roles

class RegisterSerializer(serializers.Serializer):
    phone = PhoneField(required=False, allow_null=True)
    email = serializers.EmailField(required=False, allow_null=True)
    password = serializers.CharField(write_only=True, min_length=8)
    full_name = serializers.CharField(max_length=150, required=False,
                                      allow_blank=True, default="")
    role = serializers.ChoiceField(
        choices=[User.Role.CUSTOMER, User.Role.PROVIDER],
        default=User.Role.CUSTOMER,
    )

    def validate(self, attrs):
        if not attrs.get("phone") and not attrs.get("email"):
            raise serializers.ValidationError(
                "Provide a phone number or an email address."
            )
        return attrs

class OTPSendSerializer(serializers.Serializer):
    phone = PhoneField()
    purpose = serializers.ChoiceField(
        choices=PhoneOTP.Purpose.choices,
        default=PhoneOTP.Purpose.REGISTRATION,
    )

class OTPVerifySerializer(serializers.Serializer):
    phone = PhoneField()
    code = serializers.CharField(min_length=6, max_length=6)
    purpose = serializers.ChoiceField(
        choices=PhoneOTP.Purpose.choices,
        default=PhoneOTP.Purpose.REGISTRATION,
    )

class SwitchRoleSerializer(serializers.Serializer):
    role = serializers.ChoiceField(
        choices=[User.Role.CUSTOMER, User.Role.PROVIDER]
    )

class ServoraTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["roles"] = [str(r) for r in user.roles]
        token["active_role"] = str(user.active_role)
        token["phone_verified"] = user.phone_verified
        return token

    def validate(self, attrs):
        data = super().validate(attrs)

        if self.user.is_suspended:
            raise serializers.ValidationError(
                "This account has been suspended."
            )

        data["user"] = UserSerializer(self.user).data
        return data

class ServoraTokenRefreshSerializer(TokenRefreshSerializer):
    def validate(self, attrs):
        user_id = self.token_class(attrs["refresh"]).payload.get(
            api_settings.USER_ID_CLAIM
        )
        if User.objects.filter(pk=user_id,
                               suspended_at__isnull=False).exists():
            raise AuthenticationFailed("This account has been suspended.",
                                       code="user_suspended")
        return super().validate(attrs)
