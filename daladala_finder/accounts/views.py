from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import login, update_session_auth_hash
from django.contrib.auth import views as auth_views
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_not_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext as _
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from routes.models import Feedback, Stop

from .forms import ChangePinForm, PhoneLoginForm, PhotoForm, ProfileForm, SignUpForm
from .models import Profile, SavedTrip, StoredFile
from .photos import remove_photo, replace_photo


def _safe_next(request, fallback):
    nxt = request.POST.get("next") or request.GET.get("next")
    if nxt and url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()},
                                               require_https=request.is_secure()):
        return nxt
    return fallback


class PhoneLoginView(auth_views.LoginView):
    # Django's LoginView is already open to people who are not logged in
    template_name = "accounts/login.html"
    authentication_form = PhoneLoginForm
    redirect_authenticated_user = True


@login_not_required
def signup(request):
    if request.user.is_authenticated:
        return redirect("routes:home")
    form = SignUpForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        messages.success(request, _("Karibu, %(name)s! Your account is ready.") % {"name": user.profile.first_name})
        return redirect(_safe_next(request, reverse("routes:home")))
    return render(request, "accounts/signup.html", {"form": form, "next": request.GET.get("next", "")})


def profile(request):
    Profile.objects.get_or_create(user=request.user)
    form = ProfileForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, _("Profile saved."))
        return redirect("accounts:profile")
    stats = {
        "searches": request.user.searches.count(),
        "saved": request.user.saved_trips.count(),
        "reports": request.user.feedback_set.count(),
    }
    return render(request, "accounts/profile.html", {"form": form, "stats": stats, "photo_form": PhotoForm()})


@require_POST
def upload_photo(request):
    profile, _created = Profile.objects.get_or_create(user=request.user)
    form = PhotoForm(request.POST, request.FILES)
    if form.is_valid():
        replace_photo(profile, form.cleaned_data["photo"])
        messages.success(request, _("Profile photo saved."))
    else:
        for error in form.errors.get("photo", []):
            messages.error(request, error)
    return redirect("accounts:profile")


@require_POST
def delete_photo(request):
    remove_photo(request.user.profile)
    messages.info(request, _("Profile photo removed."))
    return redirect("accounts:profile")


def change_pin(request):
    form = ChangePinForm(request.user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        update_session_auth_hash(request, user)      # stay logged in after changing the PIN
        messages.success(request, _("PIN changed."))
        return redirect("accounts:profile")
    return render(request, "accounts/pin_change.html", {"form": form})


def my_trips(request):
    saved = request.user.saved_trips.select_related("start", "destination")
    # Latest 30 searches, one line per trip (most recent first)
    seen, history = set(), []
    for item in request.user.searches.select_related("start", "destination")[:200]:
        key = (item.start_id, item.destination_id)
        if key not in seen:
            seen.add(key)
            history.append(item)
        if len(history) == 30:
            break
    saved_keys = {(t.start_id, t.destination_id) for t in saved}
    for item in history:
        item.is_saved = (item.start_id, item.destination_id) in saved_keys
    return render(request, "accounts/my_trips.html", {
        "saved": saved, "history": history,
        "total_searches": request.user.searches.count(),
    })


@require_POST
def save_trip(request):
    start = get_object_or_404(Stop, pk=request.POST.get("start"))
    destination = get_object_or_404(Stop, pk=request.POST.get("destination"))
    trip, created = SavedTrip.objects.get_or_create(user=request.user, start=start, destination=destination)
    if not created:
        trip.delete()
        messages.info(request, _("Removed %(start)s to %(destination)s from your saved trips.") % {"start": start, "destination": destination})
    else:
        messages.success(request, _("Saved %(start)s to %(destination)s. Find it on the home page and in My trips.") % {"start": start, "destination": destination})
    return redirect(_safe_next(request, reverse("accounts:my_trips")))


@require_POST
def rename_trip(request, pk):
    trip = get_object_or_404(SavedTrip, pk=pk, user=request.user)
    trip.label = request.POST.get("label", "").strip()[:60]
    trip.save(update_fields=["label"])
    messages.success(request, _("Trip name saved."))
    return redirect("accounts:my_trips")


@require_POST
def delete_trip(request, pk):
    get_object_or_404(SavedTrip, pk=pk, user=request.user).delete()
    messages.info(request, _("Trip removed."))
    return redirect("accounts:my_trips")


@require_POST
def clear_history(request):
    request.user.searches.all().delete()
    messages.info(request, _("Search history cleared."))
    return redirect("accounts:my_trips")


# ---------------------------------------------------------------- staff dashboard
def _staff_only(request):
    if not request.user.is_staff:
        raise PermissionDenied


def dashboard(request):
    """Staff only: everyone who registered and every comment (problem report) they sent."""
    _staff_only(request)
    q = request.GET.get("q", "").strip()
    users = (get_user_model().objects.select_related("profile")
             .annotate(n_searches=Count("searches", distinct=True),
                       n_saved=Count("saved_trips", distinct=True),
                       n_reports=Count("feedback", distinct=True))
             .order_by("-date_joined"))
    if q:
        users = users.filter(Q(profile__full_name__icontains=q) | Q(username__icontains=q)
                             | Q(email__icontains=q) | Q(profile__home_area__icontains=q))

    status = request.GET.get("status", "")
    comments = Feedback.objects.select_related("user__profile", "route")
    if status in dict(Feedback.STATUS_CHOICES):
        comments = comments.filter(status=status)

    week_ago = timezone.now() - timedelta(days=7)
    all_users = get_user_model().objects
    return render(request, "accounts/dashboard.html", {
        "users": users, "q": q,
        "comments": comments, "status": status,
        "status_choices": Feedback.STATUS_CHOICES,
        "totals": {
            "users": all_users.count(),
            "new_users": all_users.filter(date_joined__gte=week_ago).count(),
            "comments": Feedback.objects.count(),
            "unread": Feedback.objects.filter(status="new").count(),
        },
    })


@require_POST
def set_comment_status(request, pk):
    _staff_only(request)
    comment = get_object_or_404(Feedback, pk=pk)
    if request.POST.get("status") in dict(Feedback.STATUS_CHOICES):
        comment.status = request.POST["status"]
        comment.save(update_fields=["status"])
    return redirect(_safe_next(request, reverse("accounts:dashboard") + "#comments"))


def media_file(request, name):
    """A profile photo from the database. Names are random and never reused, so browsers may keep it."""
    stored = get_object_or_404(StoredFile, name=name)
    response = HttpResponse(bytes(stored.content), content_type="image/jpeg" if name.endswith(".jpg") else "application/octet-stream")
    response["Cache-Control"] = "private, max-age=31536000, immutable"
    response["X-Content-Type-Options"] = "nosniff"
    return response
