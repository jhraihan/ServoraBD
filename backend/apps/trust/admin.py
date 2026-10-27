from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import TrustSnapshot

@admin.register(TrustSnapshot)
class TrustSnapshotAdmin(ModelAdmin):
    list_display = ["provider", "score", "tier", "trigger", "algo_version",
                    "created_at"]
    list_filter = ["tier", "trigger", "algo_version"]
    search_fields = ["provider__display_name"]
    readonly_fields = [f.name for f in TrustSnapshot._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
