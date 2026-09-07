"""URLConf for the profile tests: {% url %} needs the users namespace, which
the shared test ROOT_URLCONF does not mount."""

from django.urls import include, path

urlpatterns = [path("", include("phoxtail.users.urls"))]
