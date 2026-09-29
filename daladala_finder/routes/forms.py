from django import forms
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from .models import Feedback, Stop


def find_stop(text):
    """Find a stop by its name or alternative name (not case sensitive)."""
    text = (text or "").strip()
    if not text:
        return None
    exact = Stop.objects.filter(Q(name__iexact=text) | Q(alternative_name__iexact=text)).first()
    return exact or Stop.objects.filter(Q(name__icontains=text) | Q(alternative_name__icontains=text)).first()


class SearchForm(forms.Form):
    start = forms.CharField(label=_("From"), max_length=100)
    destination = forms.CharField(label=_("To"), max_length=100)

    def clean(self):
        cleaned = super().clean()
        start = find_stop(cleaned.get("start"))
        destination = find_stop(cleaned.get("destination"))
        if cleaned.get("start") and not start:
            self.add_error("start", _("We don't have this stop yet. Pick one from the list."))
        if cleaned.get("destination") and not destination:
            self.add_error("destination", _("We don't have this stop yet. Pick one from the list."))
        if start and destination and start == destination:
            raise forms.ValidationError(_("Start and destination are the same stop."))
        cleaned["start_stop"], cleaned["destination_stop"] = start, destination
        return cleaned


class FeedbackForm(forms.ModelForm):
    class Meta:
        model = Feedback
        fields = ["name", "phone", "route", "message"]
        labels = {
            "name": _("Your name (optional)"),
            "phone": _("Phone number (optional)"),
            "route": _("Which route is it about? (optional)"),
            "message": _("What is wrong or missing?"),
        }
        widgets = {"message": forms.Textarea(attrs={"rows": 4})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            css = "form-select" if isinstance(field.widget, forms.Select) else "form-control"
            field.widget.attrs["class"] = css
