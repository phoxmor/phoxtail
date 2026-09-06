import pytest
from django.db import IntegrityError, transaction
from wagtail.models import Locale, Site

from phoxtail.dashboard.models import Menu


@pytest.fixture
def site():
    return Site.objects.get(is_default_site=True)


@pytest.mark.django_db
class TestMenu:
    def test_one_menu_per_site_and_language(self, site):
        Menu.objects.create(site=site, locale=Locale.get_default())
        with pytest.raises(IntegrityError), transaction.atomic():
            Menu.objects.create(site=site, locale=Locale.get_default())

    def test_reads_as_its_site_and_language(self, site):
        menu = Menu.objects.create(site=site, locale=Locale.get_default())
        assert str(menu) == f"{site} / {Locale.get_default()}"

    def test_a_menu_starts_empty(self, site):
        menu = Menu.objects.create(site=site, locale=Locale.get_default())
        assert len(menu.items) == 0
