from django.contrib import admin
from django.contrib.auth.decorators import login_not_required
from django.urls import include, path
from django.views.i18n import set_language

from accounts.views import media_file

admin.site.site_header = "Daladala Finder Admin"
admin.site.site_title = "Daladala Finder"
admin.site.index_title = "Manage stops, routes and fares"

urlpatterns = [
    path("admin/", admin.site.urls),
    # EN/SW switch in the header (open to everyone, also on the login page)
    path("i18n/setlang/", login_not_required(set_language), name="set_language"),
    path("accounts/", include("accounts.urls")),
    # Profile photos, served from the database (see accounts/storage.py)
    path("media/<path:name>", media_file, name="media_file"),
    path("", include("routes.urls")),
]
