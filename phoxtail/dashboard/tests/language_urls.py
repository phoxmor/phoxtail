"""A language-prefixed URLconf, so the switcher has real URLs to translate."""

from django.conf.urls.i18n import i18n_patterns
from django.http import HttpResponse
from django.urls import path

urlpatterns = i18n_patterns(path("dashboard/", lambda request: HttpResponse(), name="index"))
