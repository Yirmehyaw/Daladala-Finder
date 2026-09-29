"""
Django file storage that keeps uploaded files in the database (the StoredFile table).
Used for profile photos, so they survive restarts on free hosting. Set in settings.STORAGES.
"""
import mimetypes

from django.core.files.base import ContentFile
from django.core.files.storage import Storage
from django.urls import reverse
from django.utils.deconstruct import deconstructible


@deconstructible
class DatabaseStorage(Storage):
    def _model(self):
        from .models import StoredFile          # imported here: storage loads before the apps are ready
        return StoredFile

    def _open(self, name, mode="rb"):
        stored = self._model().objects.get(name=name)
        file = ContentFile(bytes(stored.content), name=name)
        file.content_type = mimetypes.guess_type(name)[0] or "application/octet-stream"
        return file

    def _save(self, name, content):
        content.seek(0)
        data = content.read()
        self._model().objects.update_or_create(name=name, defaults={"content": data, "size": len(data)})
        return name

    def exists(self, name):
        return self._model().objects.filter(name=name).exists()

    def delete(self, name):
        self._model().objects.filter(name=name).delete()

    def size(self, name):
        return self._model().objects.values_list("size", flat=True).get(name=name)

    def url(self, name):
        return reverse("media_file", args=[name])
