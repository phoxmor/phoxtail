"""Every entry type reduced to the same five facts a template draws."""

import pytest
from wagtail.models import Locale, Page, Site

from phoxtail.dashboard.models import Menu
from phoxtail.dashboard.templatetags.phoxtail_dashboard_tags import (
    menu_entry,
    menu_holds_current_entry,
)


@pytest.fixture(autouse=True)
def wagtail_urls(settings):
    settings.ROOT_URLCONF = "phoxtail.dashboard.tests.menu_urls"


@pytest.fixture
def site():
    return Site.objects.get(is_default_site=True)


def _menu(site, *entries):
    return Menu.objects.create(site=site, locale=Locale.get_default(), items=list(entries))


def _external(url="https://example.com", **value):
    return {"type": "external_link", "value": {"url": url, **value}}


def _page_entry(page, **value):
    return {"type": "page", "value": {"page": page.id, **value}}


@pytest.fixture
def draft(site):
    return site.root_page.add_child(instance=Page(title="Unwritten", slug="unwritten", live=False))


@pytest.fixture
def live_page(site):
    return site.root_page.add_child(instance=Page(title="Live", slug="live", live=True))


@pytest.mark.django_db
class TestMenuEntry:
    def test_an_external_link_falls_back_to_its_address(self, rf, site):
        menu = _menu(site, _external())
        link = menu_entry({"request": rf.get("/")}, menu.items[0])

        assert link["url"] == "https://example.com"
        assert link["label"] == "https://example.com"
        assert link["current"] is False

    def test_a_label_overrides_the_target_name(self, rf, site):
        menu = _menu(site, _external(label="Home"))

        assert menu_entry({"request": rf.get("/")}, menu.items[0])["label"] == "Home"

    def test_open_in_new_tab_is_carried_through(self, rf, site):
        menu = _menu(site, _external(open_in_new_tab=True))

        assert menu_entry({"request": rf.get("/")}, menu.items[0])["new_tab"] is True

    def test_a_page_being_read_is_marked_current(self, rf, site, live_page):
        menu = _menu(site, _page_entry(live_page))
        request = rf.get(live_page.url)

        assert menu_entry({"request": request}, menu.items[0])["current"] is True

    def test_an_encoded_path_still_matches_the_page_it_names(self, rf, site):
        """A Greek slug arrives percent-encoded and must compare equal to itself."""
        page = site.root_page.add_child(instance=Page(title="Καλά", slug="καλά", live=True))
        menu = _menu(site, _page_entry(page))
        request = rf.get("/%CE%BA%CE%B1%CE%BB%CE%AC/")

        assert menu_entry({"request": request}, menu.items[0])["current"] is True

    def test_a_draft_is_hidden_from_someone_who_could_not_publish_it(self, rf, site, draft):
        from django.contrib.auth.models import AnonymousUser

        menu = _menu(site, _page_entry(draft))
        request = rf.get("/")
        request.user = AnonymousUser()

        assert menu_entry({"request": request}, menu.items[0]) is None

    def test_a_draft_is_shown_to_an_editor_as_a_preview(self, rf, site, draft, django_user_model):
        menu = _menu(site, _page_entry(draft))
        request = rf.get("/")
        request.user = django_user_model.objects.create_superuser(username="ed", email="ed@example.com", password="pw")

        link = menu_entry({"request": request}, menu.items[0])

        assert link["unpublished"] is True
        assert str(draft.id) in link["url"]


@pytest.mark.django_db
class TestMenuHoldsCurrentEntry:
    def test_true_when_a_child_is_the_page_being_read(self, rf, site, live_page):
        menu = _menu(
            site,
            {"type": "dropdown", "value": {"label": "More", "items": [_page_entry(live_page)]}},
        )
        request = rf.get(live_page.url)

        assert menu_holds_current_entry({"request": request}, menu.items[0].value["items"])

    def test_false_when_nothing_inside_is_current(self, rf, site):
        menu = _menu(
            site,
            {"type": "dropdown", "value": {"label": "More", "items": [_external()]}},
        )

        assert not menu_holds_current_entry({"request": rf.get("/")}, menu.items[0].value["items"])


@pytest.mark.django_db
class TestMenuTemplates:
    """The menu templates are rendered, not merely parsed.

    A multi-line ``{# #}`` is not a Django comment — the lexer matches it
    line by line — so one renders as visible text on the page while the
    template still compiles without complaint.
    """

    TEMPLATES = [
        "phoxtail_dashboard/navigation/menu.html",
        "phoxtail_dashboard/navigation/menu_drawer.html",
    ]

    @pytest.fixture
    def rendered(self, rf, site, live_page):
        from django.template.loader import render_to_string

        menu = _menu(
            site,
            _page_entry(live_page, label="Home"),
            _external(label="Elsewhere"),
            {
                "type": "dropdown",
                "value": {"label": "About", "items": [_external(label="Team")]},
            },
        )
        request = rf.get("/")

        def _render(template):
            return render_to_string(template, {"dashboard_menu": menu, "request": request})

        return _render

    @pytest.mark.parametrize("template", TEMPLATES)
    def test_no_template_source_leaks_into_the_page(self, rendered, template):
        html = rendered(template)

        assert "{#" not in html
        assert "{%" not in html

    @pytest.mark.parametrize("template", TEMPLATES)
    def test_every_entry_is_drawn(self, rendered, template):
        html = rendered(template)

        assert "Home" in html
        assert "Elsewhere" in html
        assert "About" in html
        assert "Team" in html


@pytest.mark.django_db
class TestEmptyMenuSection:
    """An empty menu must not leave a section behind.

    Each drawer section carries the rule that parts it from the one above,
    so a section that renders empty draws a divider with nothing under it.
    """

    @staticmethod
    def _drawer(menu, rf):
        from django.template.loader import render_to_string

        return render_to_string(
            "phoxtail_dashboard/navigation/menu_drawer.html",
            {"dashboard_menu": menu, "request": rf.get("/")},
        )

    def test_an_empty_menu_draws_no_section(self, rf, site):
        assert "dash-menu-drawer" not in self._drawer(_menu(site), rf)

    def test_no_menu_at_all_draws_no_section(self, rf):
        assert "dash-menu-drawer" not in self._drawer(None, rf)

    def test_a_written_menu_draws_its_section(self, rf, site):
        html = self._drawer(_menu(site, _external(label="Home")), rf)

        assert "dash-menu-drawer" in html
        assert "Home" in html
