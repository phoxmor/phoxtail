"""Text people saved, written into CSS.

The site's design reaches every page as a ``<style>`` element built from the
database: font names, fallback lists, role identifiers, font file addresses.
A browser ends that element at the first ``</style``, whatever the CSS around
it says, so each value is written here the way the CSS syntax serialises it
(CSSOM, "serialize a string"), with ``<`` escaped too: nothing written here
contains ``<``, whatever was saved.

The patterns below keep such values out in the first place, with an error a
person can act on: the models' validators and the API's schemas share them.
"""

from __future__ import annotations

import re

from django.core.validators import RegexValidator, validate_slug
from django.utils.translation import gettext_lazy as _

# A font's name: letters and digits of any script, spaces and hyphens
# ("Source Sans 3", "M PLUS 1p").
FONT_NAME = r"[^\W_](?:[^\W_]|[ -])*"

# A fallback list: names separated by commas, each bare, in single or in
# double quotes ("Georgia, 'Times New Roman', -apple-system, serif").
_FALLBACK_ITEM = rf" *(?:-?{FONT_NAME}|'{FONT_NAME}'|\"{FONT_NAME}\") *"
FALLBACK = rf"{_FALLBACK_ITEM}(?:,{_FALLBACK_ITEM})*"

# A role's identifier, the middle of a variable's name (--font-heading):
# Django's slug.
IDENTIFIER = r"[-a-zA-Z0-9_]+"

validate_font_name = RegexValidator(
    rf"\A{FONT_NAME}\Z",
    _("Use letters, digits, spaces and hyphens."),
)
validate_fallback = RegexValidator(
    rf"\A{FALLBACK}\Z",
    _("Use font names separated by commas; a name may be in quotes."),
)
validate_identifier = validate_slug

# A bare word CSS reads as one name or keyword (serif, -apple-system).
_BARE = re.compile(r"-?[A-Za-z_][A-Za-z0-9_-]*")


def _hex(char: str) -> str:
    return f"\\{ord(char):x} "


def string(value: str) -> str:
    """A CSS string: the value in double quotes, nothing in it able to end it."""
    out = []
    for char in value:
        if char == "\0":
            out.append("�")
        elif char in '"\\':
            out.append("\\" + char)
        elif char == "<" or char < " " or char == "\x7f":
            out.append(_hex(char))
        else:
            out.append(char)
    return '"' + "".join(out) + '"'


def name(value: str) -> str:
    """Part of a custom property's name: letters, digits, - and _ as they are."""
    out = []
    for char in value:
        if char == "\0":
            out.append("�")
        elif char.isascii() and not (char.isalnum() or char in "-_"):
            out.append(_hex(char))
        else:
            out.append(char)
    return "".join(out)


def url(value: str) -> str:
    return f"url({string(value)})"


def font_family(family: str, fallback: str = "") -> str:
    """A font-family value: the family quoted, then its fallback list.

    Each bare word of the list stays bare, as CSS reads a generic family
    (serif) only unquoted; any other name is written as a string.
    """
    names = [string(family)]
    for item in fallback.split(","):
        item = item.strip()
        if len(item) >= 2 and item[0] == item[-1] and item[0] in "'\"":
            names.append(string(item[1:-1]))
        elif _BARE.fullmatch(item):
            names.append(item)
        elif item:
            names.append(string(item))
    return ", ".join(names)
