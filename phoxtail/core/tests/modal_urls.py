"""A URLconf with one localized view, for the modal language tests.

Mirrors the shape the dashboard now has: content lives behind a language
prefix while the modal endpoint that fetches it does not.
"""

from django.conf.urls.i18n import i18n_patterns
from django.http import HttpResponse
from django.urls import path
from django.utils.translation import get_language


def probe(request):
    return HttpResponse(get_language())


urlpatterns = i18n_patterns(path("probe/", probe, name="probe"))
