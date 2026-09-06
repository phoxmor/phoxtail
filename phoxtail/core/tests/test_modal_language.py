"""The modal endpoint reads its language from the URL it was asked to fetch."""

import pytest
from django.utils.translation import override

from phoxtail.core.views import get_core_modal_with_htmx


@pytest.fixture
def localized_urls(settings):
    settings.ROOT_URLCONF = "phoxtail.core.tests.modal_urls"


@pytest.fixture
def flat_urls(settings):
    settings.ROOT_URLCONF = "phoxtail.core.tests.modal_urls_flat"


def _modal(rf, content_url):
    request = rf.get("/modal/", {"content_url": content_url}, headers={"hx-request": "true"})
    return get_core_modal_with_htmx(request)


def test_prefixed_content_url_resolves_against_another_active_language(rf, localized_urls):
    """The bug: the cookie said one language, the content URL named another."""
    with override("en"):
        response = _modal(rf, "/el/probe/")

    assert response.status_code != 400, response.content


@pytest.mark.parametrize("language", ["en", "el"])
def test_content_is_rendered_in_the_language_the_url_names(rf, localized_urls, language):
    with override("en" if language == "el" else "el"):
        response = _modal(rf, f"/{language}/probe/")

    assert language.encode() in response.content


def test_unprefixed_content_url_keeps_the_active_language(rf, flat_urls):
    """override(None) would deactivate translation entirely — it must not."""
    with override("el"):
        response = _modal(rf, "/probe/")

    assert b"el" in response.content
