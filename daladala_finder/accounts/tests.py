from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from routes.models import Feedback, Stop
from routes.services import road_paths

from .models import SavedTrip, SearchHistory
from .phone import normalize_phone, pretty_phone
from .pin import MAX_WRONG_TRIES, validate_pin

User = get_user_model()
PIN = "4827"


def no_osrm(a, b):
    raise OSError("no internet in tests")


class PhoneTests(TestCase):
    def test_formats_become_one_number(self):
        for raw in ["0712345678", "0712 345 678", "712345678", "255712345678", "+255 712-345-678"]:
            self.assertEqual(normalize_phone(raw), "+255712345678")

    def test_bad_numbers_rejected(self):
        for raw in ["12345", "0812345678", "abc", ""]:
            with self.assertRaises(Exception):
                normalize_phone(raw)

    def test_pretty(self):
        self.assertEqual(pretty_phone("+255712345678"), "0712 345 678")


@mock.patch.object(road_paths, "fetch_from_osrm", no_osrm)
class LoginRequiredTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("load_sample_data", verbosity=0)

    def test_pages_need_login(self):
        for url in [reverse("routes:home"), reverse("routes:route_list"), reverse("routes:feedback"),
                    reverse("accounts:my_trips"), reverse("accounts:profile"),
                    reverse("routes:search") + "?start=DIT&destination=Mwenge"]:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 302, url)
            self.assertTrue(response["Location"].startswith(reverse("accounts:login")), url)

    def test_login_and_signup_pages_are_open(self):
        self.assertEqual(self.client.get(reverse("accounts:login")).status_code, 200)
        self.assertEqual(self.client.get(reverse("accounts:signup")).status_code, 200)

    def test_admin_login_is_open(self):
        self.assertEqual(self.client.get(reverse("admin:login")).status_code, 200)


@mock.patch.object(road_paths, "fetch_from_osrm", no_osrm)
class SignUpLoginTests(TestCase):
    def signup(self, **extra):
        data = {"full_name": "Asha Juma", "phone": "0712 345 678", "email": "", "home_area": "Kimara",
                "pin1": PIN, "pin2": PIN}
        data.update(extra)
        return self.client.post(reverse("accounts:signup"), data)

    def test_signup_creates_user_profile_and_logs_in(self):
        response = self.signup()
        self.assertRedirects(response, reverse("routes:home"), fetch_redirect_response=False)
        user = User.objects.get(username="+255712345678")
        self.assertEqual(user.profile.full_name, "Asha Juma")
        self.assertEqual(user.profile.home_area, "Kimara")
        self.assertNotEqual(user.password, PIN)            # stored as a hash
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)

    def test_same_phone_cannot_sign_up_twice(self):
        self.signup()
        self.client.logout()
        response = self.signup(phone="+255712345678")
        self.assertContains(response, "already exists")
        self.assertEqual(User.objects.count(), 1)

    def test_pins_must_match_be_4_digits_and_not_easy(self):
        self.assertContains(self.signup(pin2="4828"), "not the same")
        self.assertContains(self.signup(pin1="48271", pin2="48271"), "exactly 4 numbers")
        self.assertContains(self.signup(pin1="ab12", pin2="ab12"), "exactly 4 numbers")
        self.assertContains(self.signup(pin1="1234", pin2="1234"), "too easy")
        self.assertEqual(User.objects.count(), 0)

    def test_login_with_any_phone_format(self):
        User.objects.create_user("+255712345678", password=PIN)
        response = self.client.post(reverse("accounts:login"), {"username": "0712 345 678", "password": PIN})
        self.assertRedirects(response, reverse("routes:home"), fetch_redirect_response=False)

    def test_wrong_password(self):
        User.objects.create_user("+255712345678", password=PIN)
        response = self.client.post(reverse("accounts:login"), {"username": "0712345678", "password": "nope"})
        self.assertContains(response, "Wrong phone number or PIN")

    def test_logout(self):
        user = User.objects.create_user("+255712345678", password=PIN)
        self.client.force_login(user)
        self.client.post(reverse("accounts:logout"))
        self.assertEqual(self.client.get(reverse("routes:home")).status_code, 302)

    def test_createsuperuser_style_user_gets_profile(self):
        admin = User.objects.create_superuser("+255700000000", password=PIN)
        self.assertTrue(hasattr(admin, "profile"))


@mock.patch.object(road_paths, "fetch_from_osrm", no_osrm)
class UserDataTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("load_sample_data", verbosity=0)
        cls.asha = User.objects.create_user("+255712345678", password=PIN)
        cls.juma = User.objects.create_user("+255765432100", password=PIN)

    def setUp(self):
        self.client.force_login(self.asha)
        self.dit, self.mwenge = Stop.objects.get(name="DIT"), Stop.objects.get(name="Mwenge")

    def search(self):
        return self.client.get(reverse("routes:search"), {"start": "DIT", "destination": "Mwenge"})

    def test_search_is_saved_in_history(self):
        self.search()
        item = SearchHistory.objects.get(user=self.asha)
        self.assertEqual((item.start, item.destination), (self.dit, self.mwenge))
        self.assertGreater(item.options_found, 0)
        self.assertIsNotNone(item.cheapest_fare)
        self.assertContains(self.client.get(reverse("accounts:my_trips")), "DIT &rarr; Mwenge")

    def test_history_is_private(self):
        self.search()
        self.client.force_login(self.juma)
        self.assertNotContains(self.client.get(reverse("accounts:my_trips")), "DIT &rarr; Mwenge")

    def test_save_and_unsave_trip(self):
        data = {"start": self.dit.pk, "destination": self.mwenge.pk}
        self.client.post(reverse("accounts:save_trip"), data)
        self.assertTrue(SavedTrip.objects.filter(user=self.asha).exists())
        self.assertContains(self.search(), "Saved")
        self.assertContains(self.client.get(reverse("routes:home")), "Your trips")
        self.client.post(reverse("accounts:save_trip"), data)          # tap again = remove
        self.assertFalse(SavedTrip.objects.filter(user=self.asha).exists())

    def test_rename_trip(self):
        trip = SavedTrip.objects.create(user=self.asha, start=self.dit, destination=self.mwenge)
        self.client.post(reverse("accounts:rename_trip", args=[trip.pk]), {"label": "To college"})
        trip.refresh_from_db()
        self.assertEqual(trip.label, "To college")

    def test_cannot_touch_someone_elses_trip(self):
        trip = SavedTrip.objects.create(user=self.juma, start=self.dit, destination=self.mwenge)
        self.assertEqual(self.client.post(reverse("accounts:delete_trip", args=[trip.pk])).status_code, 404)
        self.assertTrue(SavedTrip.objects.filter(pk=trip.pk).exists())

    def test_clear_history(self):
        self.search()
        self.client.post(reverse("accounts:clear_history"))
        self.assertFalse(SearchHistory.objects.filter(user=self.asha).exists())

    def test_feedback_is_linked_to_user(self):
        self.client.post(reverse("routes:feedback"), {"name": "", "phone": "", "route": "", "message": "Fare changed"})
        self.assertEqual(Feedback.objects.get().user, self.asha)

    def test_profile_update(self):
        self.client.post(reverse("accounts:profile"), {"full_name": "Asha M. Juma", "email": "asha@example.com",
                                                      "home_area": "Sinza"})
        self.asha.refresh_from_db()
        self.assertEqual(self.asha.profile.full_name, "Asha M. Juma")
        self.assertEqual(self.asha.email, "asha@example.com")

    def test_change_pin(self):
        response = self.client.post(reverse("accounts:pin_change"), {
            "old_pin": PIN, "new_pin1": "9051", "new_pin2": "9051"})
        self.assertRedirects(response, reverse("accounts:profile"), fetch_redirect_response=False)
        self.asha.refresh_from_db()
        self.assertTrue(self.asha.check_password("9051"))
        self.assertEqual(self.client.get(reverse("routes:home")).status_code, 200)   # still logged in

    def test_change_pin_needs_correct_old_pin(self):
        response = self.client.post(reverse("accounts:pin_change"), {
            "old_pin": "0007", "new_pin1": "9051", "new_pin2": "9051"})
        self.assertContains(response, "current PIN is not correct")


class PinRuleTests(TestCase):
    def test_good_pins(self):
        for pin in ["4827", "9051", "0379", "7702"]:
            validate_pin(pin)

    def test_bad_pins(self):
        for pin in ["123", "12345", "12a4", "", "0000", "9999", "1234", "4321", "5678", "1212", "2580"]:
            with self.assertRaises(Exception, msg=pin):
                validate_pin(pin)


class LockoutTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("+255712345678", password=PIN)

    def login(self, pin):
        return self.client.post(reverse("accounts:login"), {"username": "0712345678", "password": pin})

    def test_account_locks_after_too_many_wrong_pins(self):
        for _ in range(MAX_WRONG_TRIES - 1):
            self.assertContains(self.login("0000"), "Wrong phone number or PIN")
        self.assertContains(self.login("0000"), "locked")
        # even the right PIN does not work while locked
        response = self.login(PIN)
        self.assertContains(response, "locked")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_lock_ends_after_time(self):
        for _ in range(MAX_WRONG_TRIES):
            self.login("0000")
        profile = self.user.profile
        profile.refresh_from_db()
        profile.locked_until = profile.locked_until - timedelta(minutes=16)
        profile.save()
        self.assertRedirects(self.login(PIN), reverse("routes:home"), fetch_redirect_response=False)

    def test_correct_pin_resets_count(self):
        for _ in range(MAX_WRONG_TRIES - 1):
            self.login("0000")
        self.login(PIN)
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.wrong_pin_count, 0)

    def test_old_long_password_still_works(self):
        User.objects.create_user("+255700000001", password="an-old-long-password")
        response = self.client.post(reverse("accounts:login"),
                                    {"username": "0700000001", "password": "an-old-long-password"})
        self.assertRedirects(response, reverse("routes:home"), fetch_redirect_response=False)


@mock.patch.object(road_paths, "fetch_from_osrm", no_osrm)
class DashboardTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = User.objects.create_user("+255700000009", password="a-strong-admin-password", is_staff=True)
        cls.asha = User.objects.create_user("+255712345678", password=PIN, email="asha@example.com")
        cls.asha.profile.full_name, cls.asha.profile.home_area = "Asha Juma", "Kimara"
        cls.asha.profile.save()
        cls.comment = Feedback.objects.create(user=cls.asha, message="The fare to Posta is now 700.")

    def test_staff_sees_users_and_comments(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse("accounts:dashboard"))
        self.assertContains(response, "Asha Juma")
        self.assertContains(response, "0712 345 678")
        self.assertContains(response, "Kimara")
        self.assertContains(response, "The fare to Posta is now 700.")

    def test_search_users(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse("accounts:dashboard"), {"q": "nobody-like-this"})
        self.assertNotContains(response, "asha@example.com")     # email is only in the users table
        self.assertContains(response, "No users found.")
        self.assertContains(self.client.get(reverse("accounts:dashboard"), {"q": "kimara"}), "asha@example.com")

    def test_change_comment_status(self):
        self.client.force_login(self.staff)
        self.client.post(reverse("accounts:set_comment_status", args=[self.comment.pk]), {"status": "fixed"})
        self.comment.refresh_from_db()
        self.assertEqual(self.comment.status, "fixed")

    def test_normal_users_are_blocked(self):
        self.client.force_login(self.asha)
        self.assertEqual(self.client.get(reverse("accounts:dashboard")).status_code, 403)
        response = self.client.post(reverse("accounts:set_comment_status", args=[self.comment.pk]), {"status": "fixed"})
        self.assertEqual(response.status_code, 403)
        self.comment.refresh_from_db()
        self.assertEqual(self.comment.status, "new")


def make_image(width=1200, height=800, fmt="JPEG", with_gps=False):
    from io import BytesIO

    from django.core.files.uploadedfile import SimpleUploadedFile
    from PIL import Image
    image = Image.new("RGB", (width, height), (15, 118, 110))
    exif = Image.Exif()
    exif[0x0112] = 6                                  # "rotate 90 degrees", like a phone held upright
    if with_gps:
        exif[0x8825] = {1: "S", 2: (6.0, 48.0, 0.0)}  # GPS latitude (Dar es Salaam)
    out = BytesIO()
    image.save(out, fmt, exif=exif) if fmt == "JPEG" else image.save(out, fmt)
    return SimpleUploadedFile("me." + fmt.lower(), out.getvalue(), content_type="image/" + fmt.lower())


@mock.patch.object(road_paths, "fetch_from_osrm", no_osrm)
class ProfilePhotoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user("+255712345678", password=PIN)
        cls.user.profile.full_name = "Asha Juma"
        cls.user.profile.save()

    def setUp(self):
        self.client.force_login(self.user)

    def upload(self, file):
        return self.client.post(reverse("accounts:upload_photo"), {"photo": file})

    def test_photo_is_square_small_upright_and_clean(self):
        from PIL import Image
        self.upload(make_image(with_gps=True))
        self.user.profile.refresh_from_db()
        self.assertTrue(self.user.profile.photo.name.startswith("profile_photos/"))
        with self.user.profile.photo.open() as file, Image.open(file) as saved:
            self.assertEqual(saved.size, (400, 400))
            self.assertEqual(saved.format, "JPEG")
            self.assertEqual(len(saved.getexif()), 0)       # no GPS, no rotation tag left
        self.assertContains(self.client.get(reverse("accounts:profile")), self.user.profile.photo.url)
        served = self.client.get(self.user.profile.photo.url)          # photo comes from the database
        self.assertEqual(served["Content-Type"], "image/jpeg")
        self.assertEqual(len(b"".join(served)), self.user.profile.photo.size)

    def test_png_works(self):
        self.upload(make_image(300, 500, fmt="PNG"))
        self.user.profile.refresh_from_db()
        self.assertTrue(self.user.profile.photo)

    def test_not_an_image_is_refused(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        response = self.upload(SimpleUploadedFile("virus.jpg", b"MZ this is not a picture"))
        self.user.profile.refresh_from_db()
        self.assertFalse(self.user.profile.photo)
        self.assertContains(self.client.get(response.url), "not a photo")

    def test_new_photo_deletes_old_file_and_remove_works(self):
        from .models import StoredFile
        self.upload(make_image())
        self.user.profile.refresh_from_db()
        first = self.user.profile.photo.name
        self.upload(make_image())
        self.user.profile.refresh_from_db()
        self.assertFalse(StoredFile.objects.filter(name=first).exists())
        self.assertEqual(StoredFile.objects.count(), 1)
        self.client.post(reverse("accounts:delete_photo"))
        self.user.profile.refresh_from_db()
        self.assertFalse(self.user.profile.photo)
        self.assertEqual(StoredFile.objects.count(), 0)
        self.assertEqual(self.client.get("/media/" + first).status_code, 404)

    def test_photos_need_login(self):
        self.upload(make_image())
        self.user.profile.refresh_from_db()
        self.client.logout()
        self.assertEqual(self.client.get(self.user.profile.photo.url).status_code, 302)   # sent to log in
