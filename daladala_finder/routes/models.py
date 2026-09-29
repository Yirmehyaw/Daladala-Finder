from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class Stop(models.Model):
    """A daladala stop, e.g. 'Ubungo Mataa' or 'Magomeni Mapipa'."""

    name = models.CharField(max_length=100, unique=True)
    alternative_name = models.CharField(
        max_length=100, blank=True,
        help_text="Other name people use for this stop (optional).",
    )
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        # If the stop was moved on the map, its saved road paths are wrong now: delete them
        if self.pk:
            old = Stop.objects.filter(pk=self.pk).values("latitude", "longitude").first()
            if old and (old["latitude"] != self.latitude or old["longitude"] != self.longitude):
                RoadSegment.objects.filter(models.Q(from_stop=self) | models.Q(to_stop=self)).delete()
        super().save(*args, **kwargs)


class Route(models.Model):
    """A daladala route, e.g. 'Kimara - Posta'. Daladalas run both directions."""

    name = models.CharField(max_length=120, unique=True)
    via = models.CharField(max_length=120, blank=True, help_text="e.g. 'via Morogoro Road'")
    fare = models.PositiveIntegerField(help_text="Full-route fare in TSh.")
    color = models.CharField(
        max_length=7, default="#1f6f8b",
        help_text="Stripe colour shown on the map, like the painted band on a daladala.",
    )
    is_active = models.BooleanField(default=True)
    stops = models.ManyToManyField(Stop, through="RouteStop", related_name="routes")

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def ordered_stops(self):
        """Stops of this route in travel order."""
        return [rs.stop for rs in self.route_stops.select_related("stop").order_by("sequence")]


class RouteStop(models.Model):
    """Links a stop to a route and says WHERE on the route it is (1st, 2nd, 3rd...)."""

    route = models.ForeignKey(Route, on_delete=models.CASCADE, related_name="route_stops")
    stop = models.ForeignKey(Stop, on_delete=models.CASCADE, related_name="route_stops")
    sequence = models.PositiveIntegerField(help_text="Order of the stop on the route (1 = first).")

    class Meta:
        ordering = ["route", "sequence"]
        unique_together = [("route", "sequence"), ("route", "stop")]

    def __str__(self):
        return f"{self.route} #{self.sequence}: {self.stop}"


class Fare(models.Model):
    """Optional: a cheaper fare for part of a route (short trips)."""

    route = models.ForeignKey(Route, on_delete=models.CASCADE, related_name="fares")
    from_stop = models.ForeignKey(Stop, on_delete=models.CASCADE, related_name="+")
    to_stop = models.ForeignKey(Stop, on_delete=models.CASCADE, related_name="+")
    amount = models.PositiveIntegerField(help_text="Fare in TSh.")

    def __str__(self):
        return f"{self.route}: {self.from_stop} to {self.to_stop} = TSh {self.amount}"


class Feedback(models.Model):
    """Reports from commuters, e.g. 'this route no longer passes Fire'."""

    STATUS_CHOICES = [("new", _("New")), ("checked", _("Checked")), ("fixed", _("Fixed"))]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                             help_text="The logged-in person who sent it.")
    name = models.CharField(max_length=80, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    route = models.ForeignKey(Route, on_delete=models.SET_NULL, null=True, blank=True)
    message = models.TextField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="new")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "feedback"

    def __str__(self):
        return f"{self.created_at:%d %b %Y} - {self.message[:40]}"


class RoadSegment(models.Model):
    """
    The real road path between two neighbouring stops, so the map follows the roads
    instead of drawing a straight line. Filled automatically from OSRM (free road routing)
    the first time it is needed, then saved here so it is only fetched once.
    """

    from_stop = models.ForeignKey(Stop, on_delete=models.CASCADE, related_name="+")
    to_stop = models.ForeignKey(Stop, on_delete=models.CASCADE, related_name="+")
    path = models.JSONField(help_text="List of [latitude, longitude] points along the road.")
    distance_m = models.PositiveIntegerField(default=0, help_text="Road distance in metres.")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("from_stop", "to_stop")]

    def __str__(self):
        return f"{self.from_stop} to {self.to_stop} ({self.distance_m / 1000:.1f} km)"
