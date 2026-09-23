"""A design list costs the same number of queries at any length.

A palette names its set, a font weight its family, and a palette set or a
font family counts what it holds; each arrives with the list's query, and a
lookup per row is what would creep back without a count.
"""

from __future__ import annotations

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from phoxtail.design.models import FontFamily, FontWeight, Palette, PaletteSet

pytestmark = pytest.mark.django_db

SHADES = {f"shade_{shade}": "#000000" for shade in (50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 950)}


def _queries(client, path):
    client.get(path)  # once untimed: per-process caches are not a cost per row
    with CaptureQueriesContext(connection) as captured:
        response = client.get(path)
    assert response.status_code == 200
    return len(captured.captured_queries), response.json()["total"]


def _same_at_one_and_five(client, path, add):
    add(0, 1)
    few, few_total = _queries(client, path)
    add(1, 4)
    many, many_total = _queries(client, path)
    assert many_total == few_total + 4
    return few, many


def _palettes(start, count):
    for index in range(start, start + count):
        palette_set = PaletteSet.objects.create(name=f"Set {index}", identifier=f"set-{index}")
        Palette.objects.create(palette_set=palette_set, title=f"Palette {index}", **SHADES)


def _weights(start, count):
    for index in range(start, start + count):
        family = FontFamily.objects.create(name=f"Family {index}")
        # No file: its URL costs no query, and a saved file would outlive the test.
        FontWeight.objects.create(family=family, weight=400, style="normal")


@pytest.mark.parametrize(
    "path, add",
    [
        ("/design/v1/palettes/", _palettes),
        ("/design/v1/palette-sets/", _palettes),
        ("/design/v1/font-weights/", _weights),
        ("/design/v1/font-families/", _weights),
    ],
)
def test_a_design_list_does_not_grow_per_row(client, path, add):
    few, many = _same_at_one_and_five(client, path, add)

    assert many == few
