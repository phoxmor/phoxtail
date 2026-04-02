from django.urls import include, path

from .registry import registry
from .views import dashboard_view

app_name = "dashboard"

urlpatterns = [
    path("", dashboard_view, name="index"),
]

for url_prefix, url_patterns in registry.get_url_patterns():
    urlpatterns.append(path(url_prefix, include((url_patterns, url_prefix.strip("/")))))
