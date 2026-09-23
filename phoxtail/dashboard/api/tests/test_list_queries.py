"""The menu list costs the same number of queries at any length.

Each menu names its site and language; both arrive with the list's query.
"""

from __future__ import annotations

from django.db import connection
from django.test.utils import CaptureQueriesContext
from wagtail.models import Locale

from phoxtail.dashboard.models import Menu


def _queries(client):
    client.get("/dashboard/v1/menus/")  # once untimed: per-process caches are not a cost per row
    with CaptureQueriesContext(connection) as captured:
        response = client.get("/dashboard/v1/menus/")
    assert response.status_code == 200
    return len(captured.captured_queries), response.json()["total"]


def test_the_menu_list_does_not_grow_per_menu(client, site):
    locales = [Locale.objects.get_or_create(language_code=code)[0] for code in ("en", "el", "de", "fr", "it")]
    Menu.objects.create(site=site, locale=locales[0])
    few, few_total = _queries(client)
    for locale in locales[1:]:
        Menu.objects.create(site=site, locale=locale)
    many, many_total = _queries(client)

    assert many_total == few_total + 4
    assert many == few
