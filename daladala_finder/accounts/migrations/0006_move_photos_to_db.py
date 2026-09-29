"""Copy profile photos saved on disk (before photos moved into the database) into StoredFile."""
from django.conf import settings
from django.db import migrations


def move_photos(apps, schema_editor):
    Profile = apps.get_model("accounts", "Profile")
    StoredFile = apps.get_model("accounts", "StoredFile")
    for profile in Profile.objects.exclude(photo=""):
        path = settings.MEDIA_ROOT / profile.photo.name
        if path.is_file() and not StoredFile.objects.filter(name=profile.photo.name).exists():
            data = path.read_bytes()
            StoredFile.objects.create(name=profile.photo.name, content=data, size=len(data))


class Migration(migrations.Migration):
    dependencies = [("accounts", "0005_stored_files")]
    operations = [migrations.RunPython(move_photos, migrations.RunPython.noop)]
