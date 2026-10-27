from django.contrib import admin

from .models import (
    Booking, BookingEvent, ProviderResponse, RequestPhoto, ServiceRequest,
)

class BookingEventInline(admin.TabularInline):
    model = BookingEvent
    extra = 0
    readonly_fields = ["from_state", "to_state", "actor", "actor_user",
                       "reason", "metadata", "created_at"]
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False

@admin.register(ServiceRequest)
class ServiceRequestAdmin(admin.ModelAdmin):
    list_display = ["id", "customer", "service", "location", "state",
                    "expires_at", "created_at"]
    list_filter = ["state", "kind"]
    search_fields = ["customer__user__phone", "service__name"]
    readonly_fields = [f.name for f in ServiceRequest._meta.fields]

    def has_add_permission(self, request):
        return False

@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ["id", "provider", "customer", "state", "scheduled_for",
                    "agreed_price", "final_price"]
    list_filter = ["state"]
    search_fields = ["provider__display_name", "customer__user__phone"]
    readonly_fields = [f.name for f in Booking._meta.fields]
    inlines = [BookingEventInline]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

@admin.register(ProviderResponse)
class ProviderResponseAdmin(admin.ModelAdmin):
    list_display = ["request", "provider", "decision", "response_seconds",
                    "created_at"]
    list_filter = ["decision"]
    readonly_fields = [f.name for f in ProviderResponse._meta.fields]

    def has_add_permission(self, request):
        return False

@admin.register(BookingEvent)
class BookingEventAdmin(admin.ModelAdmin):
    list_display = ["booking", "from_state", "to_state", "actor",
                    "created_at"]
    list_filter = ["actor", "to_state"]
    readonly_fields = [f.name for f in BookingEvent._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

@admin.register(RequestPhoto)
class RequestPhotoAdmin(admin.ModelAdmin):
    list_display = ["request", "created_at"]
