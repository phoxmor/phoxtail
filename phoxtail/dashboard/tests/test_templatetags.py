import pytest
from django.template.loader import render_to_string
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


class TestLanguageFlyout:
    """The sidebar's language row and the card it opens."""

    @staticmethod
    def _render(rf, settings, languages, active="en"):
        settings.USE_I18N = True
        settings.LANGUAGES = languages
        settings.ROOT_URLCONF = "phoxtail.dashboard.tests.language_urls"
        with override(active):
            return render_to_string(
                "phoxtail_dashboard/navigation/language_flyout.html",
                {"request": rf.get("/en/dashboard/")},
            )

    def test_the_row_names_the_language_being_read(self, rf, settings):
        html = self._render(rf, settings, [("en", "English"), ("el", "Greek")], active="el")

        row = html.split('id="dash-language-flyout"')[0]
        assert "Ελληνικά" in row
        assert "English" not in row

    def test_the_card_offers_each_language_with_this_page_in_it(self, rf, settings):
        html = self._render(rf, settings, [("en", "English"), ("el", "Greek")])

        assert 'name="next" value="/en/dashboard/"' in html
        assert 'name="next" value="/el/dashboard/"' in html
        assert html.count("dash-lang__option--active") == 1

    def test_a_single_language_draws_nothing(self, rf, settings):
        html = self._render(rf, settings, [("en", "English")])

        assert html.strip() == ""


class TestPageTitle:
    """A page is titled by the nav entry it belongs to."""

    PATHS = {"dashboard:index": "/dashboard/", "projects": "/dashboard/projects/", "new": "/dashboard/projects/new/"}

    @pytest.fixture(autouse=True)
    def _urls(self, monkeypatch):
        from django.urls import NoReverseMatch

        def reverse(name):
            if name not in self.PATHS:
                raise NoReverseMatch(name)
            return self.PATHS[name]

        monkeypatch.setattr("django.urls.reverse", reverse)

    @staticmethod
    def _render(rf, path, **extra):
        from phoxtail.dashboard.registry import DashboardNavItem

        items = [
            DashboardNavItem(label="Projects", url_name="projects", icon="folder"),
            DashboardNavItem(label="New project", url_name="new", icon="plus"),
            DashboardNavItem(label="Gone", url_name="gone", icon="close"),
        ]
        return render_to_string(
            "phoxtail_dashboard/page_title.html",
            {"request": rf.get(path), "dashboard_nav_items": items, **extra},
        )

    def test_the_longest_address_the_path_starts_with_wins(self, rf):
        html = self._render(rf, "/dashboard/projects/new/")

        assert "New project" in html
        assert 'id="icon-plus"' in html

    def test_a_page_under_an_entry_takes_its_icon_and_its_own_title(self, rf):
        html = self._render(rf, "/dashboard/projects/42/", page_title="Garden")

        assert "Garden" in html
        assert "Projects" not in html
        assert 'id="icon-folder"' in html

    def test_dashboard_names_only_itself(self, rf):
        assert "Dashboard" in self._render(rf, "/dashboard/")

    def test_a_page_with_no_entry_draws_what_it_passes(self, rf):
        html = self._render(rf, "/users/profile/", page_title="Profile", page_icon="person")

        assert "Profile" in html
        assert 'id="icon-person"' in html
