from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import BasePermission

from apps.accounts.authentication import ServoraJWTAuthentication
from apps.accounts.models import User
from apps.common.admin_site import is_verified

ADMIN_AUTHENTICATION = [ServoraJWTAuthentication, SessionAuthentication]


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
    message = ("Administrator access needs a staff account signed in to "
               "the admin with two-factor verification.")

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and user.is_staff
            and not user.is_suspended
            and is_verified(user)
        )
