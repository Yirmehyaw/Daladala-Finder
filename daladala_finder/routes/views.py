from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _

from accounts.models import SavedTrip, SearchHistory
from accounts.phone import pretty_phone

from .forms import FeedbackForm, SearchForm
from .models import Route, Stop
from .services.road_paths import path_for_stops
from .services.route_finder import find_journeys

# Quick-search buttons on the home page (only shown if both stops exist in the database)
POPULAR_TRIPS = [
    ("DIT", "Mwenge"),
    ("Kimara", "Kariakoo"),
    ("Posta", "Mbagala Rangi Tatu"),
    ("Buguruni", "Tegeta"),
]


def _stops_for_map(stops):
    return [{"name": s.name, "lat": float(s.latitude), "lng": float(s.longitude), "id": s.pk} for s in stops]


def _routes_for_map():
    routes = Route.objects.filter(is_active=True).prefetch_related("route_stops__stop")
    result = []
    for r in routes:
        stops = [rs.stop for rs in r.route_stops.all()]
        # fetch=False: the home page only uses road paths already saved, so it always loads fast
        result.append({"route": r.name, "color": r.color, "id": r.pk,
                       "stops": _stops_for_map(stops), "path": path_for_stops(stops, fetch=False)})
    return result


def _home_context(request, form):
    stops = Stop.objects.all()
    names = set(stops.values_list("name", flat=True))
    return {
        "saved_trips": request.user.saved_trips.select_related("start", "destination")[:6],
        "recent_searches": _recent_searches(request.user, 4),
        "form": form,
        "all_stops": stops,
        "map_stops": _stops_for_map(stops),
        "map_routes": _routes_for_map(),
        "route_count": Route.objects.filter(is_active=True).count(),
        "stop_count": len(names),
        "popular_trips": [(a, b) for a, b in POPULAR_TRIPS if a in names and b in names],
    }


def home(request):
    """Module 1: search form + map of all stops and routes."""
    form = SearchForm(initial={"start": request.GET.get("start", ""),
                               "destination": request.GET.get("destination", "")})
    return render(request, "routes/home.html", _home_context(request, form))


def _recent_searches(user, limit):
    """Latest different trips this person searched."""
    seen, recent = set(), []
    for item in user.searches.select_related("start", "destination")[:50]:
        key = (item.start_id, item.destination_id)
        if key not in seen:
            seen.add(key)
            recent.append(item)
        if len(recent) == limit:
            break
    return recent


def search_results(request):
    """Module 2: show journey options between two stops."""
    form = SearchForm(request.GET or None)
    if not form.is_valid():
        return render(request, "routes/home.html", _home_context(request, form))

    start = form.cleaned_data["start_stop"]
    destination = form.cleaned_data["destination_stop"]
    journeys = find_journeys(start, destination)

    # Save this search in the person's history
    SearchHistory.objects.create(
        user=request.user, start=start, destination=destination, options_found=len(journeys),
        cheapest_fare=min((j.total_fare for j in journeys), default=None))
    is_saved = SavedTrip.objects.filter(user=request.user, start=start, destination=destination).exists()

    map_journeys = [
        [{"route": leg.route.name, "color": leg.route.color, "stops": _stops_for_map(leg.stops),
          "path": path_for_stops(leg.stops)}
         for leg in journey.legs]
        for journey in journeys
    ]
    return render(request, "routes/results.html", {
        "form": form,
        "all_stops": Stop.objects.all(),
        "start": start,
        "destination": destination,
        "journeys": journeys,
        "map_journeys": map_journeys,
        "is_saved": is_saved,
    })


def route_list(request):
    """Module 3: list of all routes."""
    routes = Route.objects.filter(is_active=True).prefetch_related("route_stops__stop")
    return render(request, "routes/route_list.html", {"routes": routes})


def route_detail(request, pk):
    """Module 3b: one route with its stops in order and on the map."""
    route = get_object_or_404(Route, pk=pk)
    stops = route.ordered_stops()
    return render(request, "routes/route_detail.html", {
        "route": route,
        "stops": stops,
        "map_route": {"route": route.name, "color": route.color, "stops": _stops_for_map(stops),
                      "path": path_for_stops(stops)},
    })


def stop_detail(request, pk):
    """Module 4: which routes pass through a stop."""
    stop = get_object_or_404(Stop, pk=pk)
    routes = stop.routes.filter(is_active=True).distinct()
    return render(request, "routes/stop_detail.html", {
        "stop": stop,
        "routes": routes,
        "map_stops": _stops_for_map([stop]),
    })


def feedback(request):
    """Module 5: commuters report wrong or missing information."""
    profile = getattr(request.user, "profile", None)
    form = FeedbackForm(request.POST or None, initial={
        "route": request.GET.get("route"),
        "name": profile.full_name if profile else "",
        "phone": pretty_phone(request.user.username),
    })
    if request.method == "POST" and form.is_valid():
        report = form.save(commit=False)
        report.user = request.user
        report.save()
        messages.success(request, _("Feedback sent. Thank you, we will check it."))
        return redirect("routes:feedback")
    return render(request, "routes/feedback.html", {"form": form})
