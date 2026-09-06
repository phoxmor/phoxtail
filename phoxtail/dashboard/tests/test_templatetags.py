from django.utils.translation import override

from phoxtail.dashboard.templatetags.phoxtail_dashboard_tags import (
    dashboard_icon_path,
    dashboard_languages,
)


class TestDashboardIconPath:
    def test_returns_correct_path(self):
        result = dashboard_icon_path("calendar")
        assert result == "phoxtail_core/svgs/calendar.html"

    def test_different_icon(self):
        result = dashboard_icon_path("settings")
        assert result == "phoxtail_core/svgs/settings.html"


class TestDashboardLanguages:
    """The switcher offers every language the project serves."""

    @staticmethod
    def _options(rf, settings, languages, active="en"):
        settings.USE_I18N = True
        settings.LANGUAGES = languages
        settings.ROOT_URLCONF = "phoxtail.dashboard.tests.language_urls"
        with override(active):
            return dashboard_languages({"request": rf.get("/en/dashboard/")})

    def test_offers_each_language_with_this_page_in_it(self, rf, settings):
        options = self._options(rf, settings, [("en", "English"), ("el", "Greek")])

        assert [option["code"] for option in options] == ["en", "el"]
        assert [option["url"] for option in options] == ["/en/dashboard/", "/el/dashboard/"]

    def test_a_menu_is_not_what_makes_a_language_offerable(self, rf, settings):
        """No menus exist here at all — the platform's own screens are translated."""
        assert len(self._options(rf, settings, [("en", "English"), ("el", "Greek")])) == 2

    def test_marks_the_one_being_read(self, rf, settings):
        options = self._options(rf, settings, [("en", "English"), ("el", "Greek")], active="el")

        assert [option["code"] for option in options if option["active"]] == ["el"]

    def test_a_single_language_has_nothing_to_choose_between(self, rf, settings):
        assert self._options(rf, settings, [("en", "English")]) == []

    def test_without_i18n_there_is_nowhere_to_switch_to(self, rf, settings):
        settings.USE_I18N = False
        settings.LANGUAGES = [("en", "English"), ("el", "Greek")]
        assert dashboard_languages({"request": rf.get("/dashboard/")}) == []
