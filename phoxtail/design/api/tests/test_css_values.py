"""The API refuses values that would be written into every page's CSS.

Font names, fallback lists, role identifiers and palette colours reach the
``<style>`` on every page. The schemas use the patterns the models'
validators use (``phoxtail.design.css``), so a bad value is a 422 naming the
field, and the API document shows each rule. The MCP tools call this API.
"""

from __future__ import annotations

import pytest

from phoxtail.design.models import FontFamily, FontRole, Palette, PaletteRole, PaletteSet

HOSTILE = "Inter</style><script>alert(1)</script>"
SHADES = {f"shade_{s}": "#3b82f6" for s in (50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 950)}


def _refused_field(response) -> str:
    assert response.status_code == 422, response.json()
    (error,) = response.json()["detail"]
    return error["loc"][-1]


class TestFontFamilies:
    def test_a_real_name_and_fallback_are_created(self, client):
        response = client.post(
            "/design/v1/font-families/",
            json={"name": "Source Sans 3", "fallback": "Georgia, 'Times New Roman', serif"},
        )

        assert response.status_code == 201

    @pytest.mark.parametrize("field,value", [("name", HOSTILE), ("fallback", "serif; } </style>")])
    def test_a_hostile_value_is_refused(self, client, field, value):
        payload = {"name": "Inter", "fallback": "serif", field: value}

        response = client.post("/design/v1/font-families/", json=payload)

        assert _refused_field(response) == field
        assert not FontFamily.objects.exists()

    def test_a_patch_is_held_to_the_same_rule(self, client):
        family = FontFamily.objects.create(name="Inter")
        etag = client.get(f"/design/v1/font-families/{family.pk}/").headers["ETag"]

        response = client.patch(
            f"/design/v1/font-families/{family.pk}/", json={"name": HOSTILE}, headers={"If-Match": etag}
        )

        assert _refused_field(response) == "name"
        family.refresh_from_db()
        assert family.name == "Inter"

    def test_a_duplicate_name_is_still_a_conflict(self, client):
        FontFamily.objects.create(name="Inter")

        response = client.post("/design/v1/font-families/", json={"name": "Inter"})

        assert response.status_code == 409


@pytest.mark.parametrize(
    "path,model", [("/design/v1/font-roles/", FontRole), ("/design/v1/palette-roles/", PaletteRole)]
)
def test_a_role_identifier_must_be_a_slug(client, path, model):
    response = client.post(path, json={"name": "Heading", "identifier": "</style>"})

    assert _refused_field(response) == "identifier"
    assert not model.objects.exists()


@pytest.mark.parametrize(
    "path,payload,field",
    [
        ("/design/v1/font-families/", {"name": "A" * 101}, "name"),
        ("/design/v1/font-families/", {"name": "Inter", "fallback": "serif, " * 40 + "serif"}, "fallback"),
        ("/design/v1/font-roles/", {"name": "Heading", "identifier": "a" * 51}, "identifier"),
    ],
)
def test_a_value_longer_than_its_column_is_refused(client, path, payload, field):
    """Not a database error: the column's length is part of the field's rule."""
    assert _refused_field(client.post(path, json=payload)) == field


def test_a_palette_colour_must_be_a_hex_triplet(client):
    palette_set = PaletteSet.objects.create(name="Set", identifier="set")

    response = client.post(
        "/design/v1/palettes/",
        json={"palette_set_id": palette_set.pk, "title": "Blue", **SHADES, "shade_500": '#"><b>'},
    )

    assert _refused_field(response) == "shade_500"
    assert not Palette.objects.exists()
