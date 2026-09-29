from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin

from .models import Profile, SavedTrip, SearchHistory

User = get_user_model()


class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False


admin.site.unregister(User)


@admin.register(User)
class PhoneUserAdmin(UserAdmin):
    """Users log in with their phone number (stored in the username field as +255...)."""
    inlines = [ProfileInline]
    list_display = ["username", "full_name", "email", "date_joined", "last_login", "is_staff"]
    search_fields = ["username", "email", "profile__full_name"]

    @admin.display(description="Full name")
    def full_name(self, obj):
        return getattr(getattr(obj, "profile", None), "full_name", "")


@admin.register(SearchHistory)
class SearchHistoryAdmin(admin.ModelAdmin):
    list_display = ["searched_at", "user", "start", "destination", "options_found", "cheapest_fare"]
    list_filter = ["searched_at"]
    search_fields = ["user__username", "start__name", "destination__name"]
    date_hierarchy = "searched_at"


@admin.register(SavedTrip)
class SavedTripAdmin(admin.ModelAdmin):
    list_display = ["user", "start", "destination", "label", "created_at"]
    search_fields = ["user__username", "start__name", "destination__name", "label"]
