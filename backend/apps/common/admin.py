from django.contrib import admin
from django.contrib.admin.models import LogEntry
from django.contrib.auth.admin import GroupAdmin as BaseGroupAdmin
from django.contrib.auth.models import Group
from django_otp.plugins.otp_totp.models import TOTPDevice
from unfold.admin import ModelAdmin
from unfold.decorators import display

admin.site.unregister(Group)
admin.site.unregister(TOTPDevice)


@admin.register(Group)
class GroupAdmin(BaseGroupAdmin, ModelAdmin):
    def has_add_permission(self, request):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


@admin.register(TOTPDevice)
class TOTPDeviceAdmin(ModelAdmin):
    list_display = ["user", "name", "confirmed", "created_at", "last_used_at"]
    list_filter = ["confirmed"]
    search_fields = ["user__phone", "user__email", "user__full_name"]
    fields = ["user", "name", "confirmed", "created_at", "last_used_at"]
    readonly_fields = fields

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(LogEntry)
class LogEntryAdmin(ModelAdmin):
    list_display = ["action_time", "user", "content_type", "object_repr",
                    "action_flag", "message"]
    list_filter = ["action_flag", "content_type"]
    search_fields = ["object_repr", "change_message", "user__phone",
                     "user__full_name"]
    date_hierarchy = "action_time"
    fields = ["action_time", "user", "content_type", "object_id",
              "object_repr", "action_flag", "message"]
    readonly_fields = fields

    @display(description="What changed")
    def message(self, obj):
        return obj.get_change_message()

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
