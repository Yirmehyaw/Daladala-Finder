"""
Loads SAMPLE stops and routes so you can test the system.

IMPORTANT: coordinates are approximate and fares are example values only.
Replace them with the data you collect in the field (and LATRA's official fares).

Run:  python manage.py load_sample_data
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from routes.models import Route, RouteStop, Stop

# name, alternative name, latitude, longitude  (APPROXIMATE - verify on a map!)
STOPS = [
    ("Posta", "Posta Mpya", -6.8163, 39.2893),
    ("DIT", "Chuo cha Ufundi", -6.8147, 39.2800),
    ("Mnazi Mmoja", "", -6.8196, 39.2803),
    ("Kariakoo", "Kariakoo Sokoni", -6.8196, 39.2728),
    ("Gerezani", "", -6.8262, 39.2761),
    ("Fire", "Fire Station", -6.8150, 39.2690),
    ("Magomeni Mapipa", "Mapipa", -6.8045, 39.2560),
    ("Manzese", "Manzese Tip Top", -6.7960, 39.2340),
    ("Ubungo Mataa", "Ubungo", -6.7880, 39.2155),
    ("Kimara", "Kimara Mwisho", -6.7760, 39.1650),
    ("Kinondoni", "", -6.7870, 39.2620),
    ("Morocco", "", -6.7755, 39.2630),
    ("Mwenge", "", -6.7700, 39.2280),
    ("Mbezi Beach", "Africana", -6.7280, 39.2230),
    ("Tegeta", "Tegeta Nyuki", -6.6600, 39.1950),
    ("Buguruni", "", -6.8350, 39.2450),
    ("Mtoni", "Mtoni kwa Azizi Ali", -6.8600, 39.2730),
    ("Mbagala Rangi Tatu", "Rangi Tatu", -6.8990, 39.2700),
]

# route name, via, full fare (TSh, EXAMPLE), stripe colour, stops in order
ROUTES = [
    ("Kimara - Posta", "via Morogoro Road", 700, "#1F6F8B",
     ["Kimara", "Ubungo Mataa", "Manzese", "Magomeni Mapipa", "Fire", "DIT", "Posta"]),
    ("Ubungo - Kariakoo", "via Morogoro Road", 600, "#C2410C",
     ["Ubungo Mataa", "Manzese", "Magomeni Mapipa", "Fire", "Kariakoo"]),
    ("Mwenge - Posta", "via Kinondoni", 600, "#15803D",
     ["Mwenge", "Morocco", "Kinondoni", "Magomeni Mapipa", "Mnazi Mmoja", "Posta"]),
    ("Tegeta - Mwenge", "via Bagamoyo Road", 600, "#7C3AED",
     ["Tegeta", "Mbezi Beach", "Mwenge"]),
    ("Ubungo - Mwenge", "via Sam Nujoma Road", 500, "#BE185D",
     ["Ubungo Mataa", "Mwenge"]),
    ("Kariakoo - Mbagala", "via Kilwa Road", 600, "#A16207",
     ["Kariakoo", "Gerezani", "Mtoni", "Mbagala Rangi Tatu"]),
    ("Buguruni - Posta", "via Kariakoo", 500, "#0F766E",
     ["Buguruni", "Kariakoo", "Mnazi Mmoja", "Posta"]),
]


class Command(BaseCommand):
    help = "Load sample Dar es Salaam stops and daladala routes (for testing)."

    def add_arguments(self, parser):
        parser.add_argument("--if-empty", action="store_true",
                            help="Only load when there are no stops yet (safe to run on every deploy).")

    @transaction.atomic
    def handle(self, *args, **options):
        if options["if_empty"] and Stop.objects.exists():
            self.stdout.write("Stops already exist, sample data not loaded.")
            return
        stops = {}
        for name, alt, lat, lng in STOPS:
            stop, _ = Stop.objects.update_or_create(
                name=name, defaults={"alternative_name": alt, "latitude": lat, "longitude": lng})
            stops[name] = stop

        for name, via, fare, color, stop_names in ROUTES:
            route, _ = Route.objects.update_or_create(
                name=name, defaults={"via": via, "fare": fare, "color": color, "is_active": True})
            route.route_stops.all().delete()
            for sequence, stop_name in enumerate(stop_names, start=1):
                RouteStop.objects.create(route=route, stop=stops[stop_name], sequence=sequence)

        self.stdout.write(self.style.SUCCESS(
            f"Loaded {len(STOPS)} stops and {len(ROUTES)} routes (sample data - verify before use)."))
