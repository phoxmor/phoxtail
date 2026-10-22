"""Country names from babel, in the language being read.

The phone prefixes already take their names from babel, which carries the
Unicode consortium's country data for every language. django_countries
keeps its own names and translations, which lag behind (a renamed country
can stay untranslated for years), so the country list beside the prefixes
disagreed with them. ``COUNTRIES_OVERRIDE``, django_countries' documented
setting for renaming countries, takes lazy names; these are resolved through
babel when read, so every country field shows the names the prefixes show.

django_countries sorts names by their ASCII letters unless the pyuca package
is installed, which leaves a list in another script unsorted; pyuca holds
about 10 MB in every process. Our own forms put their lists in dictionary
order instead, as the prefixes are.
"""

from __future__ import annotations

import unicodedata

from django.utils.functional import lazy

from phoxtail.core.dates import active_locale


def _name(code, fallback) -> str:
    return active_locale().territories.get(code) or str(fallback)


_lazy_name = lazy(_name, str)


def countries_override() -> dict:
    """``COUNTRIES_OVERRIDE`` naming every country through babel.

    A language babel does not know reads the site's default language, as
    the phone prefixes and dates do. Only names change: each country keeps
    django_countries' codes and other data.
    """
    from django_countries.data import COUNTRIES

    return {code: {"name": _lazy_name(code, name)} for code, name in COUNTRIES.items()}


def alphabetical(name):
    """A name as a dictionary orders it: accents do not move a letter ("Κάτω" after "Καζ")."""
    return "".join(c for c in unicodedata.normalize("NFD", name) if not unicodedata.combining(c)).casefold()


def in_dictionary_order(choices):
    """``choices`` with the blank choice first and the rest by :func:`alphabetical` name."""
    choices = [(value, str(label)) for value, label in choices]
    blank = [choice for choice in choices if not choice[0]]
    return blank + sorted((choice for choice in choices if choice[0]), key=lambda choice: alphabetical(choice[1]))
