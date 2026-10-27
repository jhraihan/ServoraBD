from django import forms
from django.contrib import admin
from django.shortcuts import get_object_or_404
from unfold.admin import ModelAdmin, TabularInline
from unfold.decorators import action

from apps.common.admin_actions import ConfirmForm, ReasonForm, perform

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

class ReviewEditInline(TabularInline):
    model = ReviewEdit
    extra = 0
    readonly_fields = ["previous_rating", "previous_comment", "created_at"]
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False

@admin.register(Review)
class ReviewAdmin(ModelAdmin):
    list_display = ["id", "provider", "rating", "is_hidden", "published_at",
                    "created_at"]
    list_filter = ["is_hidden", "rating"]
    search_fields = ["provider__display_name", "comment"]
    form = ReviewModerationForm
    readonly_fields = [f.name for f in Review._meta.fields
                       if f.name not in ("is_hidden", "hidden_reason")]
    inlines = [ReviewEditInline]
    actions_detail = ["hide", "unhide"]

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

    @action(description="Hide", url_path="hide", icon="visibility_off",
            permissions=["change"],
            dialog={"title": "Hide this review",
                    "description": "It disappears from the provider's "
                                   "public profile and stops counting "
                                   "towards their trust score.",
                    "form_class": ReasonForm,
                    "form_submit_text": "Hide"})
    def hide(self, request, form, object_id):
        review = get_object_or_404(Review, pk=object_id)
        reason = form.cleaned_data["reason"]
        return perform(
            self, request, review,
            lambda: services.hide_review(review_id=review.pk,
                                         admin_user_id=request.user.pk,
                                         reason=reason),
            "Hidden: %s" % reason,
        )

    @action(description="Show again", url_path="unhide",
            icon="visibility", permissions=["change"],
            dialog={"title": "Show this review again",
                    "form_class": ConfirmForm,
                    "form_submit_text": "Show"})
    def unhide(self, request, form, object_id):
        review = get_object_or_404(Review, pk=object_id)
        return perform(
            self, request, review,
            lambda: services.unhide_review(review_id=review.pk,
                                           admin_user_id=request.user.pk),
            "Shown again.",
        )

@admin.register(ProviderReply)
class ProviderReplyAdmin(ModelAdmin):
    list_display = ["review", "provider", "created_at"]

@admin.register(CustomerRating)
class CustomerRatingAdmin(ModelAdmin):
    list_display = ["booking", "customer", "rating", "published_at"]
    list_filter = ["rating"]

@admin.register(ReviewEdit)
class ReviewEditAdmin(ModelAdmin):
    list_display = ["review", "previous_rating", "created_at"]
    readonly_fields = [f.name for f in ReviewEdit._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
