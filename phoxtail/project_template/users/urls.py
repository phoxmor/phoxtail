from django.urls import path

from . import views

app_name = "users"

urlpatterns = [
    path("profile/", views.profile_view, name="profile"),
    path(
        "profile/update-form/",
        views.profile_update_form_view,
        name="profile_update_form",
    ),
    path("profile/update/", views.profile_update_view, name="profile_update"),
]
