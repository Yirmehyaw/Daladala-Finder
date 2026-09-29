"""
Download the road paths for every route, so the map follows the roads.

Run:  python manage.py fetch_road_paths
      python manage.py fetch_road_paths --refresh   (download again, e.g. after moving stops)
"""
import time

from django.core.management.base import BaseCommand

from routes.models import RoadSegment, Route
from routes.services import road_paths


class Command(BaseCommand):
    help = "Get real road paths between neighbouring stops from OSRM (free) and save them."

    def add_arguments(self, parser):
        parser.add_argument("--refresh", action="store_true", help="Delete saved paths and download again.")

    def handle(self, *args, **options):
        if options["refresh"]:
            RoadSegment.objects.all().delete()

        pairs = []
        for route in Route.objects.filter(is_active=True):
            stops = route.ordered_stops()
            pairs.extend(zip(stops, stops[1:]))

        new, failed = 0, 0
        for a, b in pairs:
            known = RoadSegment.objects.filter(from_stop=a, to_stop=b).exists() or \
                RoadSegment.objects.filter(from_stop=b, to_stop=a).exists()
            if known:
                continue
            road_paths._last_failure = 0       # always try in this command
            path = road_paths.segment_path(a, b)
            if len(path) > 2:
                new += 1
                self.stdout.write(f"  {a} -> {b}: {len(path)} points")
            else:
                failed += 1
                self.stdout.write(self.style.WARNING(f"  {a} -> {b}: could not download (straight line for now)"))
            time.sleep(0.3)                    # be polite to the free server

        total = RoadSegment.objects.count()
        msg = f"Road paths: {new} downloaded, {total} saved in total."
        if failed:
            self.stdout.write(self.style.WARNING(msg + f" {failed} failed - check your internet and run again."))
        else:
            self.stdout.write(self.style.SUCCESS(msg))
