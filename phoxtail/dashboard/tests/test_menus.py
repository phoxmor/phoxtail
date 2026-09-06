import pytest
from wagtail.models import Locale, Site

from phoxtail.dashboard.menus import menu_for
from phoxtail.dashboard.models import Menu


@pytest.fixture
def site():
    return Site.objects.get(is_default_site=True)


@pytest.fixture
def greek():
    return Locale.objects.create(language_code="el")


@pytest.mark.django_db
class TestMenuFor:
    def test_finds_the_menu_written_for_that_language(self, site):
        menu = Menu.objects.create(site=site, locale=Locale.get_default())
        assert menu_for(site, Locale.get_default()) == menu

    def test_absent_rather_than_answered_in_another_language(self, site, greek):
        Menu.objects.create(site=site, locale=Locale.get_default())
        assert menu_for(site, greek) is None

    def test_no_site_or_no_locale_finds_nothing(self, site):
        assert menu_for(None, Locale.get_default()) is None
        assert menu_for(site, None) is None
