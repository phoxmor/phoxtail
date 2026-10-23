"""The languages a page can be read in, and the menu that offers them."""

import pytest
from django.contrib.staticfiles import finders
from django.template.loader import render_to_string
from django.utils.translation import override

from phoxtail.core.languages import languages

TWO = [("en", "English"), ("el", "Greek")]


@pytest.fixture
def served(settings):
    def serve(languages):
        settings.USE_I18N = True
        settings.LANGUAGES = languages
        settings.ROOT_URLCONF = "phoxtail.core.tests.language_urls"

    return serve


class TestLanguages:
    """Every language the project serves, each with this page in it."""

    def test_offers_each_language_with_this_page_in_it(self, rf, served):
        served(TWO)
        with override("en"):
            options = languages(rf.get("/en/page/?next=/x/"))

        assert [option["code"] for option in options] == ["en", "el"]
        assert [option["url"] for option in options] == ["/en/page/?next=/x/", "/el/page/?next=/x/"]
        assert [option["name_local"] for option in options] == ["English", "Ελληνικά"]

    def test_marks_the_one_being_read(self, rf, served):
        served(TWO)
        with override("el"):
            options = languages(rf.get("/el/page/"))

        assert [option["code"] for option in options if option["active"]] == ["el"]

    def test_a_single_language_has_nothing_to_choose_between(self, rf, served):
        served([("en", "English")])

        assert languages(rf.get("/en/page/")) == []

    def test_without_i18n_there_is_nowhere_to_switch_to(self, rf, settings):
        settings.USE_I18N = False
        settings.LANGUAGES = TWO

        assert languages(rf.get("/page/")) == []

    def test_without_a_request_the_root_is_offered(self, served):
        served(TWO)
        with override("en"):
            options = languages(None)

        assert [option["url"] for option in options] == ["/", "/"]


class TestLanguageMenu:
    """The button that opens the list; each choice is posted to set_language."""

    @staticmethod
    def _render(rf, active="en"):
        with override(active):
            return render_to_string("phoxtail_core/language_menu.html", {"request": rf.get(f"/{active}/page/")})

    def test_each_choice_posts_its_language_and_this_page_in_it(self, rf, served):
        served(TWO)
        html = self._render(rf)

        assert html.count('action="/i18n/setlang/"') == 2
        assert 'name="next" value="/en/page/"' in html
        assert 'name="next" value="/el/page/"' in html

    def test_the_button_shows_the_language_being_read(self, rf, served):
        served(TWO)
        html = self._render(rf, active="el")

        button = html.split("phx-language-menu__list")[0]
        assert 'phx-language-menu__code">el<' in button
        assert html.count('aria-current="true"') == 1

    def test_without_set_language_published_draws_nothing(self, rf, settings):
        settings.USE_I18N = True
        settings.LANGUAGES = TWO
        settings.ROOT_URLCONF = "phoxtail.core.tests.modal_urls"

        assert self._render(rf).strip() == ""

    def test_a_single_language_draws_nothing(self, rf, served):
        served([("en", "English")])

        assert self._render(rf).strip() == ""

    def test_its_script_is_a_file_every_page_loads(self, rf, served):
        """A page with a Content-Security-Policy refuses an inline script."""
        served(TWO)

        assert "<script" not in self._render(rf)
        assert "phoxtail_core/js/language_menu.js" in render_to_string("phoxtail_core/scripts.html")
        assert finders.find("phoxtail_core/js/language_menu.js")
