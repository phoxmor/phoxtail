"""A language-prefixed URLconf, so the language menu has real URLs to translate."""

from django.conf.urls.i18n import i18n_patterns
from django.http import HttpResponse
from django.urls import include, path

urlpatterns = [
    path("i18n/", include("django.conf.urls.i18n")),
    *i18n_patterns(path("page/", lambda request: HttpResponse(), name="page")),
]
