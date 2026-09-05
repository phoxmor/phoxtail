from django.conf import settings
from django.urls import include, path
from django.utils.module_loading import import_string

from .constants import DEFAULT_INDEX_VIEW
from .registry import registry

app_name = "dashboard"

# The index view is resolved from a setting rather than imported directly: a
# site cannot shadow a Python module the way it can shadow a template, so
# without this seam the view would be the one part of the dashboard nobody
# could replace. getattr rather than a bare attribute access — the app
# config's default_settings only lands in projects that call wire_apps().
urlpatterns = [
    path("", import_string(getattr(settings, "PHOXTAIL_DASHBOARD_VIEW", DEFAULT_INDEX_VIEW)), name="index"),
]

for url_prefix, url_patterns in registry.get_url_patterns():
    urlpatterns.append(path(url_prefix, include((url_patterns, url_prefix.strip("/")))))
