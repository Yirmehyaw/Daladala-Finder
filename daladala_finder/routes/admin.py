from django.contrib import admin

from .models import Fare, Feedback, RoadSegment, Route, RouteStop, Stop


class RouteStopInline(admin.TabularInline):
    model = RouteStop
    extra = 1
    ordering = ["sequence"]
    autocomplete_fields = ["stop"]


class FareInline(admin.TabularInline):
    model = Fare
    extra = 0
    autocomplete_fields = ["from_stop", "to_stop"]


@admin.register(Stop)
class StopAdmin(admin.ModelAdmin):
    list_display = ["name", "alternative_name", "latitude", "longitude"]
    search_fields = ["name", "alternative_name"]


@admin.register(Route)
class RouteAdmin(admin.ModelAdmin):
    list_display = ["name", "via", "fare", "is_active"]
    list_filter = ["is_active"]
    list_editable = ["fare", "is_active"]
    search_fields = ["name", "via"]
    inlines = [RouteStopInline, FareInline]


@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ["created_at", "route", "message", "status"]
    list_filter = ["status", "route"]
    list_editable = ["status"]


@admin.register(RoadSegment)
class RoadSegmentAdmin(admin.ModelAdmin):
    """Saved road paths. Delete one to make the site download it again."""
    list_display = ["from_stop", "to_stop", "distance_m", "updated_at"]
    search_fields = ["from_stop__name", "to_stop__name"]
    readonly_fields = ["path"]
