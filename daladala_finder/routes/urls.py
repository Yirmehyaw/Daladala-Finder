from django.urls import path

from . import views

app_name = "routes"

urlpatterns = [
    path("", views.home, name="home"),
    path("search/", views.search_results, name="search"),
    path("routes/", views.route_list, name="route_list"),
    path("routes/<int:pk>/", views.route_detail, name="route_detail"),
    path("stops/<int:pk>/", views.stop_detail, name="stop_detail"),
    path("feedback/", views.feedback, name="feedback"),
]
