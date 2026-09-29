"""
Data saved for each person who uses the site.

The login itself uses Django's built-in User table:
  - username = the person's phone number, stored as +255XXXXXXXXX
  - password = the person's 4-digit PIN, stored safely as a hash (never as plain text).
               Admin accounts made with createsuperuser use a normal strong password.
  - email    = optional
"""
import uuid
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone

from routes.models import Stop


def photo_path(profile, filename):
    # Random name, so photos cannot be guessed and a new photo never shows an old cached one
    return f"profile_photos/{uuid.uuid4().hex}.jpg"


class Profile(models.Model):
    """Extra details about a person."""

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    full_name = models.CharField(max_length=120)
    home_area = models.CharField(max_length=100, blank=True, help_text="e.g. Kimara, Mbezi, Sinza")
    photo = models.ImageField(upload_to=photo_path, blank=True,
                              help_text="Profile picture (DP), saved as a 400x400 JPEG.")
    created_at = models.DateTimeField(auto_now_add=True)
    # Protection against guessing the 4-digit PIN
    wrong_pin_count = models.PositiveSmallIntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.full_name} ({self.user.username})"

    @property
    def phone(self):
        return self.user.username

    @property
    def first_name(self):
        return self.full_name.split()[0] if self.full_name else ""

    # ----- PIN lockout -----
    def minutes_locked(self):
        """Minutes left before the person can try again (0 = not locked)."""
        if self.locked_until and self.locked_until > timezone.now():
            return max(1, round((self.locked_until - timezone.now()).total_seconds() / 60))
        return 0

    def record_wrong_pin(self):
        from .pin import LOCK_MINUTES, MAX_WRONG_TRIES
        Profile.objects.filter(pk=self.pk).update(wrong_pin_count=models.F("wrong_pin_count") + 1)
        self.refresh_from_db(fields=["wrong_pin_count"])
        if self.wrong_pin_count >= MAX_WRONG_TRIES:
            self.locked_until = timezone.now() + timedelta(minutes=LOCK_MINUTES)
            self.wrong_pin_count = 0
            self.save(update_fields=["locked_until", "wrong_pin_count"])

    def clear_wrong_pins(self):
        if self.wrong_pin_count or self.locked_until:
            self.wrong_pin_count, self.locked_until = 0, None
            self.save(update_fields=["wrong_pin_count", "locked_until"])


class SearchHistory(models.Model):
    """Every trip a person searched for."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="searches")
    start = models.ForeignKey(Stop, on_delete=models.CASCADE, related_name="+")
    destination = models.ForeignKey(Stop, on_delete=models.CASCADE, related_name="+")
    options_found = models.PositiveSmallIntegerField(default=0)
    cheapest_fare = models.PositiveIntegerField(null=True, blank=True)
    searched_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-searched_at"]
        verbose_name_plural = "search history"
        indexes = [models.Index(fields=["user", "-searched_at"])]

    def __str__(self):
        return f"{self.user.username}: {self.start} to {self.destination}"


class SavedTrip(models.Model):
    """A trip a person starred, e.g. 'Home to DIT'."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="saved_trips")
    start = models.ForeignKey(Stop, on_delete=models.CASCADE, related_name="+")
    destination = models.ForeignKey(Stop, on_delete=models.CASCADE, related_name="+")
    label = models.CharField(max_length=60, blank=True, help_text="Optional name, e.g. 'To college'")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["user", "start", "destination"], name="unique_saved_trip"),
        ]

    def __str__(self):
        return self.label or f"{self.start} to {self.destination}"


class StoredFile(models.Model):
    """
    Uploaded files (profile photos) kept inside the database instead of on disk.
    Free hosting like Render wipes its disk on every restart, the database keeps them.
    Photos are small (a 400x400 JPEG is about 30 KB). See storage.py.
    """

    name = models.CharField(max_length=255, unique=True)
    content = models.BinaryField()
    size = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.size // 1024} KB)"
