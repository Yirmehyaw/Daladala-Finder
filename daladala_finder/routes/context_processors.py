from django.conf import settings


def google_maps(request):
    """Make the Google Maps API key available in every template as {{ google_maps_key }}."""
    return {"google_maps_key": getattr(settings, "GOOGLE_MAPS_API_KEY", "")}
