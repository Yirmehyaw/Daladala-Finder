from django import template

from ..phone import pretty_phone

register = template.Library()


@register.filter
def phone(value):
    """{{ user.username|phone }} -> 0712 345 678"""
    return pretty_phone(value)
