from rest_framework.permissions import BasePermission

from apps.accounts.models import User


class IsProvider(BasePermission):
    message = "You need a provider profile to do this."

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and not user.is_suspended
            and hasattr(user, "provider_profile")
        )


class IsAdminUser(BasePermission):
    message = "Administrator access is required."

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and user.is_staff
            and not user.is_suspended
        )
