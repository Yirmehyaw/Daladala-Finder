from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Profile


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_profile(sender, instance, created, raw=False, **kwargs):
    """Every user gets a Profile (also admins made with createsuperuser)."""
    if created and not raw:      # raw = loading a backup with loaddata (the profile comes from the file)
        Profile.objects.get_or_create(user=instance, defaults={"full_name": instance.get_full_name() or ""})
