from unittest import mock

from django.core.management import call_command
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import RoadSegment, Stop
from .services import road_paths
from .services.route_finder import find_journeys


class RouteFinderTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("load_sample_data", verbosity=0)

    def stop(self, name):
        return Stop.objects.get(name=name)

    def test_direct_route(self):
        journeys = find_journeys(self.stop("DIT"), self.stop("Kimara"))
        self.assertTrue(journeys)
        self.assertEqual(journeys[0].transfers, 0)
        self.assertEqual(journeys[0].legs[0].route.name, "Kimara - Posta")

    def test_one_transfer(self):
        journeys = find_journeys(self.stop("Posta"), self.stop("Mbagala Rangi Tatu"))
        self.assertTrue(journeys)
        self.assertEqual(journeys[0].transfers, 1)

    def test_two_transfers(self):
        journeys = find_journeys(self.stop("Tegeta"), self.stop("Kariakoo"))
        self.assertTrue(journeys)
        self.assertEqual(journeys[0].transfers, 2)

    def test_same_stop_returns_nothing(self):
        self.assertEqual(find_journeys(self.stop("DIT"), self.stop("DIT")), [])


def fake_osrm(a, b):
    """Pretend OSRM answer: a bent road through a middle point (no internet needed in tests)."""
    mid = [float(a.latitude) + 0.001, (float(a.longitude) + float(b.longitude)) / 2]
    return [[float(a.latitude), float(a.longitude)], mid, [float(b.latitude), float(b.longitude)]], 1234


@mock.patch.object(road_paths, "fetch_from_osrm", fake_osrm)
class PageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("load_sample_data", verbosity=0)
        cls.user = get_user_model().objects.create_user("+255712345678", password="4827")

    def setUp(self):
        self.client.force_login(self.user)

    def test_pages_load(self):
        for url in ["routes:home", "routes:route_list", "routes:feedback"]:
            self.assertEqual(self.client.get(reverse(url)).status_code, 200)

    def test_search_page(self):
        response = self.client.get(reverse("routes:search"), {"start": "dit", "destination": "Mwenge"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "TSh")

    def test_unknown_stop_shows_error(self):
        response = self.client.get(reverse("routes:search"), {"start": "Nowhere", "destination": "Mwenge"})
        self.assertContains(response, "We don&#x27;t have this stop yet")


@mock.patch.object(road_paths, "fetch_from_osrm", fake_osrm)
class LanguageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("load_sample_data", verbosity=0)
        cls.user = get_user_model().objects.create_user("+255712345678", password="4827")

    def test_english_by_default(self):
        response = self.client.get(reverse("accounts:login"))
        self.assertContains(response, '<html lang="en">')
        self.assertContains(response, "Log in with your phone number")

    def test_browser_language_swahili(self):
        response = self.client.get(reverse("accounts:login"), HTTP_ACCEPT_LANGUAGE="sw")
        self.assertContains(response, '<html lang="sw">')
        self.assertContains(response, "Ingia kwa namba yako ya simu")

    def test_switch_works_before_login_and_is_remembered(self):
        response = self.client.post(reverse("set_language"), {"language": "sw", "next": "/accounts/login/"})
        self.assertRedirects(response, "/accounts/login/", fetch_redirect_response=False)
        self.client.force_login(self.user)
        self.assertContains(self.client.get(reverse("routes:home")), "Tafuta daladala")
        self.client.post(reverse("set_language"), {"language": "en", "next": "/"})
        self.assertContains(self.client.get(reverse("routes:home")), "Find daladala")

    def test_results_and_errors_in_swahili(self):
        self.client.force_login(self.user)
        self.client.post(reverse("set_language"), {"language": "sw"})
        response = self.client.get(reverse("routes:search"), {"start": "Posta", "destination": "Mbagala Rangi Tatu"})
        self.assertContains(response, "Badilisha gari")
        response = self.client.get(reverse("routes:search"), {"start": "Nowhere", "destination": "Mwenge"})
        self.assertContains(response, "Bado hatuna kituo hiki")


@mock.patch.object(road_paths, "fetch_from_osrm", side_effect=fake_osrm)
class RoadPathTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("load_sample_data", verbosity=0)

    def setUp(self):
        road_paths._last_failure = 0

    def stop(self, name):
        return Stop.objects.get(name=name)

    def test_path_follows_road_and_is_saved(self, osrm):
        path = road_paths.path_for_stops([self.stop("Kimara"), self.stop("Ubungo Mataa")])
        self.assertEqual(len(path), 3)                      # bent road, not a straight line
        self.assertEqual(RoadSegment.objects.count(), 1)
        road_paths.path_for_stops([self.stop("Kimara"), self.stop("Ubungo Mataa")])
        self.assertEqual(osrm.call_count, 1)                # second time comes from the database

    def test_reverse_direction_reuses_saved_path(self, osrm):
        a, b = self.stop("Kimara"), self.stop("Ubungo Mataa")
        forward = road_paths.path_for_stops([a, b])
        backward = road_paths.path_for_stops([b, a])
        self.assertEqual(backward, list(reversed(forward)))
        self.assertEqual(osrm.call_count, 1)

    def test_joined_legs_do_not_repeat_points(self, osrm):
        stops = [self.stop("Kimara"), self.stop("Ubungo Mataa"), self.stop("Manzese")]
        self.assertEqual(len(road_paths.path_for_stops(stops)), 5)   # 3 + 3 - 1 shared point

    def test_straight_line_when_osrm_is_down(self, osrm):
        osrm.side_effect = OSError("no internet")
        path = road_paths.path_for_stops([self.stop("Kimara"), self.stop("Ubungo Mataa")])
        self.assertEqual(len(path), 2)
        self.assertEqual(RoadSegment.objects.count(), 0)    # nothing wrong saved; tries again later

    def test_moving_a_stop_deletes_its_old_paths(self, osrm):
        kimara = self.stop("Kimara")
        road_paths.path_for_stops([kimara, self.stop("Ubungo Mataa")])
        kimara.latitude = -6.7700
        kimara.save()
        self.assertEqual(RoadSegment.objects.count(), 0)

    @mock.patch("time.sleep")
    def test_fetch_command(self, sleep, osrm):
        call_command("fetch_road_paths", verbosity=0, stdout=open("/dev/null", "w"))
        self.assertGreater(RoadSegment.objects.count(), 10)
