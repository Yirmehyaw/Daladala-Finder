"""
Route-finding logic for the Daladala Finder.

How it works (explain this in your report!):
  1. Every route is a list of stops in order (from the RouteStop table).
  2. A "leg" = riding ONE daladala from stop A to stop B on the same route.
     Daladalas run in both directions, so A can come before or after B.
  3. We search by number of legs, like Breadth-First Search (BFS):
       - 1 leg  = direct route
       - 2 legs = one transfer
       - 3 legs = two transfers (and so on, up to MAX_LEGS)
     We stop at the first level that gives an answer, so the user always
     sees the options with the FEWEST changes first.
"""
from dataclasses import dataclass, field

from ..models import Fare, Route

MAX_LEGS = 4        # direct, up to 3 transfers
MAX_OPTIONS = 5     # how many journey options to show


@dataclass
class Leg:
    route: Route
    stops: list      # stops passed on this leg, in travel order
    fare: int

    @property
    def board(self):
        return self.stops[0]

    @property
    def alight(self):
        return self.stops[-1]

    @property
    def towards(self):
        """Which end of the route the daladala is heading to (what the conductor shouts)."""
        ordered = self.route._cached_stops
        return ordered[-1] if ordered.index(self.alight) > ordered.index(self.board) else ordered[0]

    @property
    def stop_count(self):
        return len(self.stops) - 1


@dataclass
class Journey:
    legs: list = field(default_factory=list)

    @property
    def total_fare(self):
        return sum(leg.fare for leg in self.legs)

    @property
    def transfers(self):
        return len(self.legs) - 1

    @property
    def total_stops(self):
        return sum(leg.stop_count for leg in self.legs)


def _load_routes():
    """Load all active routes with their stops in order (one DB query per route)."""
    routes = list(Route.objects.filter(is_active=True).prefetch_related("route_stops__stop"))
    for route in routes:
        route._cached_stops = [rs.stop for rs in sorted(route.route_stops.all(), key=lambda r: r.sequence)]
    return routes


def _fare_for(route, board, alight, fare_table):
    """Use a special short-trip fare if the admin added one, otherwise the full route fare."""
    return fare_table.get((route.id, board.id, alight.id)) or fare_table.get(
        (route.id, alight.id, board.id)) or route.fare


def _ride(route, board, alight, fare_table):
    """Build a Leg for riding `route` from `board` to `alight`."""
    stops = route._cached_stops
    i, j = stops.index(board), stops.index(alight)
    path = stops[i:j + 1] if i < j else list(reversed(stops[j:i + 1]))
    return Leg(route=route, stops=path, fare=_fare_for(route, board, alight, fare_table))


def find_journeys(start, destination):
    """Return a list of Journey options from `start` to `destination` (Stop objects)."""
    if start == destination:
        return []

    routes = _load_routes()
    fare_table = {(f.route_id, f.from_stop_id, f.to_stop_id): f.amount for f in Fare.objects.all()}
    routes_at = {}  # stop -> routes that pass through it
    for route in routes:
        for stop in route._cached_stops:
            routes_at.setdefault(stop, []).append(route)

    # Each partial journey: (current_stop, legs_so_far, routes_used, stops_visited)
    frontier = [(start, [], set(), {start})]
    results = []

    for _ in range(MAX_LEGS):
        next_frontier = []
        for stop, legs, used_routes, visited in frontier:
            for route in routes_at.get(stop, []):
                if route in used_routes:
                    continue
                for other in route._cached_stops:
                    if other in visited:
                        continue
                    leg = _ride(route, stop, other, fare_table)
                    new_legs = legs + [leg]
                    if other == destination:
                        results.append(Journey(new_legs))
                    else:
                        next_frontier.append((other, new_legs, used_routes | {route}, visited | {other}))
        if results:
            break  # found answers with the fewest transfers - stop searching deeper
        frontier = next_frontier

    # Remove duplicates (same routes in the same order) keeping the cheapest/shortest one
    best = {}
    for journey in results:
        key = tuple(leg.route.id for leg in journey.legs)
        current = best.get(key)
        if current is None or (journey.total_fare, journey.total_stops) < (current.total_fare, current.total_stops):
            best[key] = journey

    return sorted(best.values(), key=lambda j: (j.total_fare, j.total_stops))[:MAX_OPTIONS]
