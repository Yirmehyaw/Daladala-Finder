from django.conf import settings
from django.db import migrations


def create_missing_profiles(apps, schema_editor):
    """Users created before accounts were added (e.g. an admin) get a Profile too."""
    User = apps.get_model(*settings.AUTH_USER_MODEL.split("."))
    Profile = apps.get_model("accounts", "Profile")
    for user in User.objects.filter(profile__isnull=True):
        name = f"{user.first_name} {user.last_name}".strip() or user.username
        Profile.objects.create(user=user, full_name=name)


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [migrations.RunPython(create_missing_profiles, migrations.RunPython.noop)]
