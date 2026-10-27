from django.contrib import admin
from django.contrib.admin.apps import AdminConfig
from django.http import HttpResponse

from .throttling import AdminLoginThrottle


class ServoraAdminSite(admin.AdminSite):
    def has_permission(self, request):
        return (super().has_permission(request)
                and not request.user.is_suspended)

    def login(self, request, extra_context=None):
        if request.method == "POST" and \
                not AdminLoginThrottle().allow_request(request, None):
            return HttpResponse(
                "Too many login attempts. Try again in 15 minutes.",
                status=429, content_type="text/plain",
            )
        return super().login(request, extra_context)


class ServoraAdminConfig(AdminConfig):
    default_site = "apps.common.admin_site.ServoraAdminSite"
