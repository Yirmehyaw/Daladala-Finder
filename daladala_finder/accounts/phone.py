"""Tanzanian phone numbers: accept 0712 345 678, 712345678, 255712345678 or +255 712 345 678."""
import re

from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _

_PATTERN = re.compile(r"^(?:\+?255|0)?([67]\d{8})$")


def normalize_phone(value):
    """Return the number as +255XXXXXXXXX, or raise ValidationError."""
    digits = re.sub(r"[\s\-().]", "", value or "")
    match = _PATTERN.match(digits)
    if not match:
        raise ValidationError(_("Enter a valid Tanzanian mobile number, e.g. 0712 345 678."))
    return "+255" + match.group(1)


def pretty_phone(value):
    """+255712345678 -> 0712 345 678"""
    if value and value.startswith("+255") and len(value) == 13:
        local = "0" + value[4:]
        return f"{local[:4]} {local[4:7]} {local[7:]}"
    return value
