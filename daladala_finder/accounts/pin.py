"""
4-digit PIN rules and protection against guessing.

A 4-digit PIN has only 10,000 combinations, so:
  1. Very easy PINs (1234, 0000, 1111 ...) are not allowed.
  2. After MAX_WRONG_TRIES wrong PINs, the account is locked for LOCK_MINUTES.
"""
import re

from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _

MAX_WRONG_TRIES = 5
LOCK_MINUTES = 15

_WEAK_PINS = {
    "1234", "4321", "0123", "3210", "1212", "2121", "1122", "2580", "0852",
    "1004", "2000", "2001", "1010", "6969", "1313", "4444", "7777",
}


def validate_pin(pin):
    if not re.fullmatch(r"\d{4}", pin or ""):
        raise ValidationError(_("Your PIN must be exactly 4 numbers."))
    if len(set(pin)) == 1 or pin in _WEAK_PINS or pin in "0123456789" or pin in "9876543210":
        raise ValidationError(_("This PIN is too easy to guess. Choose another one."))


def pin_widget_attrs(**extra):
    """Shows the number keypad on phones and allows only 4 digits."""
    attrs = {"inputmode": "numeric", "pattern": "[0-9]{4}", "maxlength": "4",
             "autocomplete": "off", "class": "form-control form-control-lg pin-input", "placeholder": "••••"}
    attrs.update(extra)
    return attrs
