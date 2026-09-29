"""
Road paths for the map.

Instead of drawing a straight line from stop to stop, we ask OSRM (a free, open-source
road routing service that uses OpenStreetMap data) for the real road between each pair
of neighbouring stops. The answer is saved in the RoadSegment table, so every pair is
only fetched once. If OSRM cannot be reached, we fall back to a straight line and try
again later.
"""
import json
import logging
import time
import urllib.error
import urllib.request

from django.db import DatabaseError

from ..models import RoadSegment

log = logging.getLogger(__name__)

OSRM_URL = ("https://router.project-osrm.org/route/v1/driving/"
            "{lng1},{lat1};{lng2},{lat2}?overview=full&geometries=geojson")
TIMEOUT_SECONDS = 6
RETRY_AFTER_SECONDS = 300     # after a failure, wait 5 minutes before asking OSRM again
_last_failure = 0.0


def _point(stop):
    return [float(stop.latitude), float(stop.longitude)]


def fetch_from_osrm(a, b):
    """Ask OSRM for the road from stop a to stop b. Returns (path, metres)."""
    url = OSRM_URL.format(lat1=a.latitude, lng1=a.longitude, lat2=b.latitude, lng2=b.longitude)
    request = urllib.request.Request(url, headers={"User-Agent": "DaladalaFinder/1.0 (student project)"})
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        data = json.load(response)
    if data.get("code") != "Ok" or not data.get("routes"):
        raise ValueError(f"OSRM answered {data.get('code')}")
    route = data["routes"][0]
    # GeoJSON gives [longitude, latitude]; Leaflet wants [latitude, longitude]
    path = [[round(lat, 6), round(lng, 6)] for lng, lat in route["geometry"]["coordinates"]]
    return path, int(route.get("distance", 0))


def segment_path(a, b, fetch=True):
    """Road path from stop a to stop b (either direction is reused)."""
    global _last_failure
    try:
        saved = RoadSegment.objects.filter(from_stop=a, to_stop=b).first()
        if saved:
            return saved.path
        saved = RoadSegment.objects.filter(from_stop=b, to_stop=a).first()
        if saved:
            return list(reversed(saved.path))
    except DatabaseError:
        # The RoadSegment table does not exist yet (run: python manage.py migrate)
        return [_point(a), _point(b)]

    if fetch and time.time() - _last_failure > RETRY_AFTER_SECONDS:
        try:
            path, metres = fetch_from_osrm(a, b)
            RoadSegment.objects.update_or_create(
                from_stop=a, to_stop=b, defaults={"path": path, "distance_m": metres})
            return path
        except (urllib.error.URLError, OSError, ValueError, KeyError) as error:
            _last_failure = time.time()
            log.warning("Could not get road path %s -> %s: %s", a, b, error)

    return [_point(a), _point(b)]     # straight line fallback


def path_for_stops(stops, fetch=True):
    """One continuous road path through a list of stops (in travel order)."""
    stops = list(stops)
    if len(stops) < 2:
        return [_point(s) for s in stops]
    path = []
    for a, b in zip(stops, stops[1:]):
        piece = segment_path(a, b, fetch=fetch)
        path.extend(piece[1:] if path else piece)   # don't repeat the joining point
    return path
