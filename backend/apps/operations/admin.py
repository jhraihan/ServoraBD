from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import JobRun


@admin.register(JobRun)
class JobRunAdmin(ModelAdmin):
    list_display = ["job", "status", "started_at", "duration_seconds",
                    "rows_affected", "message"]
    list_filter = ["job", "status"]
    readonly_fields = [f.name for f in JobRun._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
