"""
Profile photos (DP).

Every upload is opened with Pillow and saved again as a new small JPEG:
  - turned the right way up (phones store rotation separately),
  - cut to a square from the middle and resized to SIZE x SIZE,
  - hidden data removed (phones put the GPS location of the photo inside it).
Saving a new image also means a fake "image" (e.g. a renamed program) can never be stored.
"""
from io import BytesIO

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.utils.translation import gettext as _
from PIL import Image, ImageOps, UnidentifiedImageError

SIZE = 400                       # pixels, width and height
MAX_UPLOAD_MB = 5
Image.MAX_IMAGE_PIXELS = 40_000_000   # refuse giant images that would use too much memory


def clean_photo(upload):
    """Check an uploaded file and return it as a square JPEG (ContentFile), or raise ValidationError."""
    if upload.size > MAX_UPLOAD_MB * 1024 * 1024:
        raise ValidationError(_("This photo is too big. Choose one smaller than %(mb)s MB.") % {"mb": MAX_UPLOAD_MB})
    try:
        image = Image.open(upload)
        image.load()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise ValidationError(_("This file is not a photo. Choose a JPG, PNG or WEBP picture."))

    image = ImageOps.exif_transpose(image)                    # right way up
    image = ImageOps.fit(image.convert("RGB"), (SIZE, SIZE), Image.LANCZOS)   # square from the middle
    out = BytesIO()
    image.save(out, "JPEG", quality=85, optimize=True)        # new file: no hidden data kept
    return ContentFile(out.getvalue(), name="photo.jpg")


def replace_photo(profile, photo_file):
    """Save a new photo for this profile and delete the old file."""
    old = profile.photo.name
    profile.photo.save("photo.jpg", photo_file, save=True)
    if old:
        profile.photo.storage.delete(old)


def remove_photo(profile):
    if profile.photo:
        profile.photo.delete(save=True)
