"""Pages of each locale say which language they are in, where they meet.

With several locales, the top of the page tree holds one home page per
language, and they usually share a title: three rows reading the same
name, told apart only by opening them. The Wagtail admin explorer labels
them with their locale, and so does the menu picker, on the same rule:
the children of the tree's root, and every search result, since search
lists pages of each locale side by side. Each language is named in its
own words, as the language menu names it, by Django's language_name_local.
Below the top, a page's language is its branch's, so its rows go
unlabeled.
"""

from __future__ import annotations

import pytest
from django.test import override_settings

pytestmark = [
    pytest.mark.django_db,
    pytest.mark.urls("phoxtail.cms.tests.bar_urls"),
]

LABEL = 'class="phoxtail-media-picker-menu-row-locale"'


@pytest.fixture
def operator(django_user_model):
    return django_user_model.objects.create_superuser(username="boss", email="boss@example.invalid", password="x")


@pytest.fixture
def homes():
    """The default home page and its German copy, both under the tree's root."""
    from wagtail.models import Locale, Site

    home = Site.objects.get(is_default_site=True).root_page.specific
    german = Locale.objects.create(language_code="de")
    return home, home.copy_for_translation(german)


def _menu(rf, user, **params):
    from phoxtail.agent import views

    request = rf.get("/", {"tab": "menu", **params})
    request.user = user
    request.htmx = False
    return views.media_picker(request).content.decode()


@override_settings(WAGTAIL_I18N_ENABLED=True)
def test_the_locales_home_pages_are_labeled(rf, operator, homes):
    html = _menu(rf, operator)
    assert html.count(LABEL) == 2
    assert "(Deutsch)" in html


@override_settings(WAGTAIL_I18N_ENABLED=False)
def test_a_single_language_site_shows_no_labels(rf, operator, homes):
    assert LABEL not in _menu(rf, operator)


@override_settings(WAGTAIL_I18N_ENABLED=True)
def test_pages_below_the_top_are_not_labeled(rf, operator, homes):
    from phoxtail.agent import views

    home, _ = homes
    request = rf.get("/", {"parent_id": home.pk})
    request.user = operator
    request.htmx = False
    assert LABEL not in views.menu_picker_children(request).content.decode()


@override_settings(WAGTAIL_I18N_ENABLED=True)
def test_search_results_are_labeled(rf, operator, homes):
    home, _ = homes
    html = _menu(rf, operator, q=home.title)
    rows = html.count('class="phoxtail-media-picker-menu-row-title"')
    assert rows
    assert html.count(LABEL) == rows
