"""Every country field names countries as the phone prefixes do: through babel."""

from __future__ import annotations

import babel
import pytest
from django.conf import settings
from django.utils import translation
from django_countries import Countries
from django_countries.data import COUNTRIES

# A language whose names differ from English and are written in another
# script, so that both the names and their order are really under test.
OTHER = "el"


def _names(language):
    with translation.override(language):
        return [(code, str(name)) for code, name in Countries()]


def test_the_users_app_wires_the_override():
    assert set(settings.COUNTRIES_OVERRIDE) == set(COUNTRIES)


def test_names_are_babels_in_the_language_being_read():
    for language in ("en", OTHER):
        territories = babel.Locale.parse(language).territories
        assert all(name == territories[code] for code, name in _names(language))


@pytest.mark.parametrize("form_name", ["SignupForm", "UserProfileForm"])
def test_our_forms_list_countries_in_dictionary_order(form_name):
    # django_countries sorts by ASCII letters only (pyuca is not installed),
    # so a list in another script would keep whatever order it started in.
    from phoxtail.users import forms
    from phoxtail.users.countries import alphabetical

    with translation.override(OTHER):
        choices = list(getattr(forms, form_name)().fields["country"].choices)
    names = [str(label) for value, label in choices if value]
    assert not choices[0][0]
    assert len(names) == len(COUNTRIES)
    assert names == sorted(names, key=alphabetical)


def test_a_language_babel_does_not_know_agrees_with_the_phone_prefixes():
    # Both read the site's default language. "US" because django_countries'
    # own English name for it differs from babel's.
    from phoxtail.users.forms import prefix_choices

    with translation.override("zz"):
        prefix = dict(prefix_choices())["US"].split(" ", 1)[1]
        assert Countries().name("US") == prefix


def test_only_names_change():
    countries = Countries()
    assert (countries.alpha3("DE"), countries.numeric("DE"), countries.ioc_code("DE")) == ("DEU", 276, "GER")


def test_the_country_field_offers_the_same_names_as_the_phone_prefixes():
    from phoxtail.users.forms import prefix_choices

    with translation.override(OTHER):
        prefixes = {region: label.split(" ", 1)[1] for region, label in prefix_choices() if region}
        countries = dict(_names(OTHER))
    assert all(countries[region] == name for region, name in prefixes.items() if region in countries)
