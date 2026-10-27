from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import CustomerProfile, PhoneOTP, ProviderProfile, User

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ["-date_joined"]
    list_display = ["__str__", "phone", "email", "active_role",
                    "phone_verified", "is_active", "is_staff"]
    list_filter = ["active_role", "phone_verified", "is_active", "is_staff"]
    search_fields = ["phone", "email", "full_name"]

    fieldsets = (
        (None, {"fields": ("phone", "email", "password")}),
        ("Personal", {"fields": ("full_name",)}),
        ("Verification", {"fields": ("phone_verified", "email_verified")}),
        ("Roles", {"fields": ("active_role",)}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser",
                                    "groups", "user_permissions")}),
        ("Suspension", {"fields": ("suspended_at", "suspension_reason")}),
        ("Dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("phone", "email", "full_name", "password1",
                       "password2"),
        }),
    )

    def get_readonly_fields(self, request, obj=None):
        fields = list(super().get_readonly_fields(request, obj))
        if not request.user.is_superuser:
            fields += ["is_staff", "is_superuser", "groups",
                       "user_permissions"]
        return fields

    def has_change_permission(self, request, obj=None):
        if obj is not None and obj.is_superuser and \
                not request.user.is_superuser:
            return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        if obj is not None and obj.is_superuser and \
                not request.user.is_superuser:
            return False
        return super().has_delete_permission(request, obj)

@admin.register(CustomerProfile)
class CustomerProfileAdmin(admin.ModelAdmin):
    list_display = ["__str__", "created_at"]
    search_fields = ["user__phone", "user__email", "user__full_name"]

@admin.register(ProviderProfile)
class ProviderProfileAdmin(admin.ModelAdmin):
    list_display = ["display_name", "trust_score", "trust_tier",
                    "jobs_completed", "identity_verified",
                    "is_accepting_work"]
    list_filter = ["trust_tier", "identity_verified", "is_accepting_work"]
    search_fields = ["display_name", "user__phone", "user__email"]

    readonly_fields = ["trust_score", "trust_tier", "trust_computed_at",
                       "jobs_completed", "jobs_cancelled", "jobs_accepted",
                       "requests_received", "median_response_seconds"]

@admin.register(PhoneOTP)
class PhoneOTPAdmin(admin.ModelAdmin):
    list_display = ["phone", "purpose", "created_at", "expires_at",
                    "consumed_at", "attempts"]
    list_filter = ["purpose"]
    search_fields = ["phone"]
    readonly_fields = ["code_hash", "created_at", "updated_at"]
