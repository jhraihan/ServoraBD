from django import forms
from django.contrib import admin

from . import services
from .models import CustomerRating, ProviderReply, Review, ReviewEdit

class ReviewModerationForm(forms.ModelForm):
    def clean(self):
        cleaned = super().clean()
        if cleaned.get("is_hidden") and \
                not cleaned.get("hidden_reason", "").strip():
            self.add_error("hidden_reason",
                           "Give a reason for hiding this review.")
        return cleaned

class ReviewEditInline(admin.TabularInline):
    model = ReviewEdit
    extra = 0
    readonly_fields = ["previous_rating", "previous_comment", "created_at"]
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False

@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ["id", "provider", "rating", "is_hidden", "published_at",
                    "created_at"]
    list_filter = ["is_hidden", "rating"]
    search_fields = ["provider__display_name", "comment"]
    form = ReviewModerationForm
    readonly_fields = [f.name for f in Review._meta.fields
                       if f.name not in ("is_hidden", "hidden_reason")]
    inlines = [ReviewEditInline]

    def has_add_permission(self, request):
        return False

    def save_model(self, request, obj, form, change):
        if not form.changed_data:
            return
        if obj.is_hidden:
            services.hide_review(review_id=obj.pk,
                                 admin_user_id=request.user.id,
                                 reason=obj.hidden_reason)
        else:
            services.unhide_review(review_id=obj.pk,
                                   admin_user_id=request.user.id)

@admin.register(ProviderReply)
class ProviderReplyAdmin(admin.ModelAdmin):
    list_display = ["review", "provider", "created_at"]

@admin.register(CustomerRating)
class CustomerRatingAdmin(admin.ModelAdmin):
    list_display = ["booking", "customer", "rating", "published_at"]
    list_filter = ["rating"]

@admin.register(ReviewEdit)
class ReviewEditAdmin(admin.ModelAdmin):
    list_display = ["review", "previous_rating", "created_at"]
    readonly_fields = [f.name for f in ReviewEdit._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
