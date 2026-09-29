from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("login/", views.PhoneLoginView.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),        # POST only
    path("signup/", views.signup, name="signup"),
    path("profile/", views.profile, name="profile"),
    path("pin/", views.change_pin, name="pin_change"),
    path("profile/photo/", views.upload_photo, name="upload_photo"),
    path("profile/photo/remove/", views.delete_photo, name="delete_photo"),
    path("trips/", views.my_trips, name="my_trips"),
    path("trips/save/", views.save_trip, name="save_trip"),
    path("trips/<int:pk>/rename/", views.rename_trip, name="rename_trip"),
    path("trips/<int:pk>/delete/", views.delete_trip, name="delete_trip"),
    path("history/clear/", views.clear_history, name="clear_history"),
    # Staff only
    path("dashboard/", views.dashboard, name="dashboard"),
    path("dashboard/comments/<int:pk>/status/", views.set_comment_status, name="set_comment_status"),
]
