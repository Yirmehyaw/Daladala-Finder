from django import forms
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.forms import AuthenticationForm
from django.utils.translation import gettext_lazy as _

from .models import Profile, SavedTrip
from .phone import normalize_phone
from .photos import clean_photo
from .pin import pin_widget_attrs, validate_pin

User = get_user_model()


def _style(form):
    for field in form.fields.values():
        field.widget.attrs.setdefault("class", "form-control form-control-lg")


class PhoneLoginForm(AuthenticationForm):
    """Log in with phone number + 4-digit PIN. Too many wrong PINs lock the account for a while."""

    username = forms.CharField(
        label=_("Phone number"),
        widget=forms.TextInput(attrs={"autofocus": True, "inputmode": "tel", "autocomplete": "tel",
                                      "placeholder": "0712 345 678"}))
    password = forms.CharField(
        label=_("PIN"), strip=False,
        # no maxlength here, so older accounts / admins with a longer password can still log in
        widget=forms.PasswordInput(attrs={"inputmode": "numeric", "autocomplete": "current-password",
                                          "placeholder": "••••"}))

    error_messages = {
        "invalid_login": _("Wrong phone number or PIN. Please try again."),
        "inactive": _("This account is not active."),
        "locked": _("Too many wrong PINs. For your safety this account is locked. Try again in %(minutes)s minute(s)."),
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _style(self)

    def clean_username(self):
        raw = self.cleaned_data.get("username", "")
        try:
            return normalize_phone(raw)
        except forms.ValidationError:
            return raw          # let the normal "wrong phone or PIN" message show

    def clean(self):
        username = self.cleaned_data.get("username")
        password = self.cleaned_data.get("password")
        if not (username and password):
            return self.cleaned_data

        profile = Profile.objects.filter(user__username=username).first()
        if profile and profile.minutes_locked():
            raise forms.ValidationError(self.error_messages["locked"], code="locked",
                                        params={"minutes": profile.minutes_locked()})

        self.user_cache = authenticate(self.request, username=username, password=password)
        if self.user_cache is None:
            if profile:
                profile.record_wrong_pin()
                if profile.minutes_locked():
                    raise forms.ValidationError(self.error_messages["locked"], code="locked",
                                                params={"minutes": profile.minutes_locked()})
            raise self.get_invalid_login_error()

        self.confirm_login_allowed(self.user_cache)
        if profile:
            profile.clear_wrong_pins()
        return self.cleaned_data


class SignUpForm(forms.Form):
    full_name = forms.CharField(label=_("Full name"), max_length=120,
                                widget=forms.TextInput(attrs={"autocomplete": "name", "placeholder": _("e.g. Asha Juma")}))
    phone = forms.CharField(label=_("Phone number"), max_length=20,
                            widget=forms.TextInput(attrs={"inputmode": "tel", "autocomplete": "tel",
                                                          "placeholder": "0712 345 678"}))
    email = forms.EmailField(label=_("Email (optional)"), required=False,
                             widget=forms.EmailInput(attrs={"autocomplete": "email"}))
    home_area = forms.CharField(label=_("Home area (optional)"), max_length=100, required=False,
                                widget=forms.TextInput(attrs={"placeholder": _("e.g. Kimara")}))
    pin1 = forms.CharField(label=_("Choose a 4-digit PIN"), strip=False,
                           widget=forms.PasswordInput(attrs=pin_widget_attrs()),
                           help_text=_("4 numbers. Not an easy one like 1234 or 0000."))
    pin2 = forms.CharField(label=_("Confirm PIN"), strip=False,
                           widget=forms.PasswordInput(attrs=pin_widget_attrs()))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _style(self)

    def clean_phone(self):
        phone = normalize_phone(self.cleaned_data["phone"])
        if User.objects.filter(username=phone).exists():
            raise forms.ValidationError(_("An account with this phone number already exists. Log in instead."))
        return phone

    def clean_pin1(self):
        pin = self.cleaned_data["pin1"]
        validate_pin(pin)
        return pin

    def clean(self):
        cleaned = super().clean()
        p1, p2 = cleaned.get("pin1"), cleaned.get("pin2")
        if p1 and p2 and p1 != p2:
            self.add_error("pin2", _("The two PINs are not the same."))
        return cleaned

    def save(self):
        data = self.cleaned_data
        user = User.objects.create_user(username=data["phone"], email=data.get("email", ""),
                                        password=data["pin1"])
        profile = user.profile        # created automatically (see signals.py)
        profile.full_name = data["full_name"].strip()
        profile.home_area = data.get("home_area", "").strip()
        profile.save()
        return user


class ProfileForm(forms.Form):
    full_name = forms.CharField(label=_("Full name"), max_length=120)
    email = forms.EmailField(label=_("Email (optional)"), required=False)
    home_area = forms.CharField(label=_("Home area (optional)"), max_length=100, required=False)

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        profile = user.profile
        kwargs.setdefault("initial", {"full_name": profile.full_name, "email": user.email,
                                      "home_area": profile.home_area})
        super().__init__(*args, **kwargs)
        _style(self)

    def save(self):
        data = self.cleaned_data
        self.user.email = data.get("email", "")
        self.user.save(update_fields=["email"])
        profile = self.user.profile
        profile.full_name = data["full_name"].strip()
        profile.home_area = data.get("home_area", "").strip()
        profile.save()


class PhotoForm(forms.Form):
    photo = forms.FileField(
        label=_("Profile photo"),
        widget=forms.ClearableFileInput(attrs={"accept": "image/*",
                                               "class": "form-control"}))

    def clean_photo(self):
        return clean_photo(self.cleaned_data["photo"])     # square 400x400 JPEG, hidden data removed


class SavedTripLabelForm(forms.ModelForm):
    class Meta:
        model = SavedTrip
        fields = ["label"]


class ChangePinForm(forms.Form):
    old_pin = forms.CharField(label=_("Current PIN"), strip=False,
                              widget=forms.PasswordInput(attrs={"inputmode": "numeric", "autocomplete": "current-password",
                                                                "class": "form-control form-control-lg", "autofocus": True}),
                              help_text=_("If your account still has an old password, type that instead."))
    new_pin1 = forms.CharField(label=_("New 4-digit PIN"), strip=False,
                               widget=forms.PasswordInput(attrs=pin_widget_attrs()),
                               help_text=_("4 numbers. Not an easy one like 1234 or 0000."))
    new_pin2 = forms.CharField(label=_("Confirm new PIN"), strip=False,
                               widget=forms.PasswordInput(attrs=pin_widget_attrs()))

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_old_pin(self):
        old = self.cleaned_data["old_pin"]
        if not self.user.check_password(old):
            raise forms.ValidationError(_("Your current PIN is not correct."))
        return old

    def clean_new_pin1(self):
        pin = self.cleaned_data["new_pin1"]
        validate_pin(pin)
        return pin

    def clean(self):
        cleaned = super().clean()
        p1, p2 = cleaned.get("new_pin1"), cleaned.get("new_pin2")
        if p1 and p2 and p1 != p2:
            self.add_error("new_pin2", _("The two PINs are not the same."))
        return cleaned

    def save(self):
        self.user.set_password(self.cleaned_data["new_pin1"])
        self.user.save(update_fields=["password"])
        return self.user
