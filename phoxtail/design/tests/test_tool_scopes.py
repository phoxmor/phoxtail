"""Each design tool names the codename its endpoint already names.

The endpoint decides; the tool only repeats the decision, so that a narrowed
credential is offered a catalogue matching the doors that will actually open.
If the two ever disagree the failure is quiet in both directions — a tool
offered and then refused, or one withheld that would have worked.

Pinned by reading the annotations rather than by calling anything: what is at
stake is two strings being equal, and the surest way to check that is to read
both.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_API = Path(__file__).resolve().parent.parent / "api" / "v1"
_MCP = Path(__file__).resolve().parent.parent / "mcp"

# Tool name -> the endpoint function whose act it performs. Written out rather
# than derived: the two sides disagree on word order (``palettes_list`` against
# ``list_palettes``) and on verbs (``upload`` and ``create_from_url`` against
# ``upload_font_weight`` and ``ingest_font_weight_from_url``), so a rule over
# the names would quietly pair the wrong two.
PAIRS = {
    "phoxtail_palette_sets_list": "list_palette_sets",
    "phoxtail_palette_sets_get": "get_palette_set",
    "phoxtail_palette_sets_create": "create_palette_set",
    "phoxtail_palette_sets_update": "patch_palette_set",
    "phoxtail_palette_sets_delete": "delete_palette_set",
    "phoxtail_palettes_list": "list_palettes",
    "phoxtail_palettes_get": "get_palette",
    "phoxtail_palettes_create": "create_palette",
    "phoxtail_palettes_update": "patch_palette",
    "phoxtail_palettes_delete": "delete_palette",
    "phoxtail_palette_roles_list": "list_palette_roles",
    "phoxtail_palette_roles_get": "get_palette_role",
    "phoxtail_palette_roles_create": "create_palette_role",
    "phoxtail_palette_roles_update": "patch_palette_role",
    "phoxtail_palette_roles_delete": "delete_palette_role",
    "phoxtail_font_families_list": "list_font_families",
    "phoxtail_font_families_get": "get_font_family",
    "phoxtail_font_families_create": "create_font_family",
    "phoxtail_font_families_update": "patch_font_family",
    "phoxtail_font_families_delete": "delete_font_family",
    "phoxtail_font_roles_list": "list_font_roles",
    "phoxtail_font_roles_get": "get_font_role",
    "phoxtail_font_roles_create": "create_font_role",
    "phoxtail_font_roles_update": "patch_font_role",
    "phoxtail_font_roles_delete": "delete_font_role",
    "phoxtail_font_weights_list": "list_font_weights",
    "phoxtail_font_weights_get": "get_font_weight",
    "phoxtail_font_weights_upload": "upload_font_weight",
    "phoxtail_font_weights_create_from_url": "ingest_font_weight_from_url",
    "phoxtail_font_weights_delete": "delete_font_weight",
}


def _endpoint_codenames() -> dict[str, str]:
    """``{view function: codename}`` for every guarded design endpoint."""
    found = {}
    for path in _API.glob("*.py"):
        source = path.read_text()
        for match in re.finditer(r'auth=guarded\("([^"]+)"\),\n\)\ndef (\w+)\(', source):
            found[match.group(2)] = match.group(1)
    return found


def _tool_codenames() -> dict[str, str]:
    """``{tool name: codename}`` for every scoped design tool."""
    found = {}
    for path in _MCP.glob("*.py"):
        source = path.read_text()
        for match in re.finditer(r'name="(\w+)",\n\s+auth=\[scoped\("([^"]+)"\)\]', source):
            found[match.group(1)] = match.group(2)
    return found


def test_every_endpoint_is_guarded():
    """A missing annotation is the hole this pass exists to close."""
    assert sorted(_endpoint_codenames()) == sorted(PAIRS.values())


def test_every_tool_is_scoped():
    assert sorted(_tool_codenames()) == sorted(PAIRS)


@pytest.mark.parametrize("tool,endpoint", sorted(PAIRS.items()))
def test_the_tool_names_what_its_endpoint_names(tool, endpoint):
    assert _tool_codenames()[tool] == _endpoint_codenames()[endpoint]


def test_the_two_font_weight_creators_agree():
    """Uploading a file and fetching a URL are one act with two doors.

    Both add a font weight, so both name ``add_fontweight``. Worth stating:
    they are the one pair in this domain where two endpoints share a codename,
    and a later reader could mistake that for a copy-paste slip.
    """
    codenames = _endpoint_codenames()
    assert (
        codenames["upload_font_weight"] == codenames["ingest_font_weight_from_url"] == "phoxtail_design.add_fontweight"
    )


def test_every_codename_is_a_real_permission(db):
    """A typo would refuse everyone, silently and forever.

    Django creates these rows at ``migrate`` for every model, so the
    ``auth_permission`` table is the registry and nothing else has to be kept.
    """
    from django.contrib.auth.models import Permission

    real = {
        f"phoxtail_design.{p.codename}" for p in Permission.objects.filter(content_type__app_label="phoxtail_design")
    }
    assert set(_tool_codenames().values()) <= real
    assert set(_endpoint_codenames().values()) <= real
