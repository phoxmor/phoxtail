"""Each cms tool names the codename its endpoint already names.

The endpoint decides; the tool only repeats the decision, so that a narrowed
credential is offered a catalogue matching the doors that will actually open.
If the two ever disagree the failure is quiet in both directions — a tool
offered and then refused, or one withheld that would have worked.

**cms declares in two shapes, and the difference is Wagtail's.** Where a
permission is global, the endpoint carries ``guarded()`` and both halves of
authorization are answered at the door. Where Wagtail grants per object —
pages per subtree, collections per collection, site settings per site — the
endpoint carries ``scoped()`` and the person's half is answered in the body
by Wagtail's own policy, because ``has_perm`` returns False for people
Wagtail genuinely permits. This test reads both shapes; which one an
endpoint uses is that family's decision, not this file's.

``ENDPOINTS_WITHOUT_A_CODENAME`` names what deliberately declares nothing,
so "everything is accounted for" can still be asserted.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_API = Path(__file__).resolve().parent.parent / "api" / "v1"
_MCP = Path(__file__).resolve().parent.parent / "mcp"

# Tool name -> the endpoint function whose act it performs.
PAIRS: dict[str, str] = {}

# Tools with no endpoint of their own. Each names what it actually reaches:
# an MCP tool naming no codename is offered to *every* credential, the
# opposite of the API's default, where declaring nothing closes the door.
TOOLS_WITHOUT_AN_ENDPOINT: dict[str, tuple[str, ...]] = {}

# Endpoints that name no codename because there is none to name, and say so
# with ``authenticated()`` rather than by staying silent. ``list_page_types``
# returns page type names and field schemas derived from installed code
# rather than from rows — no model, no permission, nothing to ask for. It
# still has to declare itself open: silence keeps the API-wide default,
# which refuses a scoped token, and its MCP tool is offered to every
# credential, so silence on both halves is a contradiction rather than a
# matched pair.
ENDPOINTS_WITHOUT_A_CODENAME = {"list_page_types"}

# Tools that pair with those, and so name nothing either. A bare endpoint
# with a scoped tool would withhold the tool from a credential the door
# would have admitted; a guarded endpoint with a bare tool would offer a
# tool that is then refused. Both halves bare is the only consistent pair.
TOOLS_WITHOUT_A_CODENAME = {"phoxtail_page_types_list"}

# Shrinks to nothing as cms lands, family by family. Kept so that a
# half-annotated domain cannot be mistaken for a finished one.
ENDPOINTS_NOT_YET_ANNOTATED = {
    # sites and locales — global grants, land next
    "list_sites",
    "create_site",
    "get_site",
    "patch_site",
    "delete_site",
    "list_locales",
    # collections — per-collection grants, lands with its own bug fix
    "list_collections",
    "create_collection",
    "get_collection",
    "patch_collection",
    "delete_collection",
    # site settings, fonts, palettes — per-site grants
    "get_site_setting",
    "patch_site_setting",
    "list_site_fonts",
    "create_site_font",
    "get_site_font",
    "patch_site_font",
    "delete_site_font",
    "list_site_palettes",
    "create_site_palette",
    "get_site_palette",
    "patch_site_palette",
    "delete_site_palette",
    # pages, body, blocks — per-subtree grants
    "list_pages",
    "create_page",
    "get_page",
    "patch_page",
    "publish_page",
    "unpublish_page",
    "copy_page_for_translation",
    "move_page",
    "delete_page",
    "get_body",
    "put_body",
    "get_block",
    "patch_block",
    "add_block",
    "delete_block",
    "move_block",
}


def _endpoint_codenames() -> dict[str, str | tuple[str, ...]]:
    """``{view function: codename}`` for every annotated cms endpoint.

    Reads ``guarded()`` and ``scoped()`` alike — see the module docstring for
    why cms uses both. An endpoint naming several codenames yields a tuple.
    """
    found: dict[str, str | tuple[str, ...]] = {}
    for path in _API.glob("*.py"):
        source = path.read_text()
        for match in re.finditer(
            r"auth=(?:guarded|scoped)\(\s*((?:\s*\"[^\"]+\",?\s*)+)\),?\n\)\ndef (\w+)\(",
            source,
        ):
            names = tuple(re.findall(r"\"([^\"]+)\"", match.group(1)))
            found[match.group(2)] = names[0] if len(names) == 1 else names
    return found


def _tool_codenames() -> dict[str, str | tuple[str, ...]]:
    """``{tool name: codename}`` for every scoped cms tool."""
    found: dict[str, str | tuple[str, ...]] = {}
    for path in _MCP.glob("*.py"):
        source = path.read_text()
        for match in re.finditer(r'name="(\w+)",\n\s+auth=\[scoped\(((?:\s*"[^"]+",?\s*)+)\)\]', source):
            names = tuple(re.findall(r'"([^"]+)"', match.group(2)))
            found[match.group(1)] = names[0] if len(names) == 1 else names
    return found


def _declared_tools() -> set[str]:
    """Every ``@mcp_server.tool`` name in this app, scoped or not."""
    found: set[str] = set()
    for path in _MCP.glob("*.py"):
        found.update(re.findall(r'@mcp_server\.tool\(\n\s+name="(\w+)"', path.read_text()))
    return found


def _flatten(values) -> set[str]:
    flat: set[str] = set()
    for value in values:
        flat.update((value,) if isinstance(value, str) else value)
    return flat


def _served_endpoints() -> set[str]:
    """The endpoint functions the mounted API actually serves under cms."""
    from phoxtail.api import api

    api.urls  # force the routers to build
    return {
        op.view_func.__name__
        for prefix, router in api._routers
        if prefix.startswith("cms")
        for view in router.path_operations.values()
        for op in view.operations
    }


def test_every_endpoint_is_accounted_for():
    """Annotated, deliberately bare, or still owed — never simply forgotten."""
    unaccounted = (
        _served_endpoints() - set(_endpoint_codenames()) - ENDPOINTS_WITHOUT_A_CODENAME - ENDPOINTS_NOT_YET_ANNOTATED
    )
    assert unaccounted == set()


def test_nothing_is_still_waiting_to_be_annotated():
    """Fails on purpose when cms finishes.

    When the last family lands this set empties, this test fails, and both
    it and the set are deleted. That failure is the reminder, not a defect.
    """
    assert ENDPOINTS_NOT_YET_ANNOTATED, (
        "Every cms endpoint is annotated. Delete ENDPOINTS_NOT_YET_ANNOTATED and this test."
    )


def test_the_deferral_set_names_only_real_endpoints():
    """A typo here would hide a genuinely unannotated endpoint forever."""
    assert ENDPOINTS_NOT_YET_ANNOTATED <= _served_endpoints()


def test_every_tool_is_accounted_for():
    """Scoped, or deliberately bare — a tool that is neither is offered to all."""
    still_owed = _declared_tools() - set(_tool_codenames()) - TOOLS_WITHOUT_A_CODENAME
    # Tools whose endpoint has not landed yet are bare for now, and named by
    # the endpoint deferral set rather than a second list of their own.
    assert still_owed, "every cms tool is scoped — fold this into test_every_tool_is_scoped"


def test_the_bare_pair_is_the_only_bare_pair():
    """A tool may be bare only because its endpoint deliberately is too.

    Every other bare tool in this app is bare because its endpoint has not
    landed yet, and the deferral set is what says so.
    """
    assert TOOLS_WITHOUT_A_CODENAME == {"phoxtail_page_types_list"}


@pytest.mark.parametrize("tool,endpoint", sorted(PAIRS.items()))
def test_the_tool_names_what_its_endpoint_names(tool, endpoint):
    assert _tool_codenames()[tool] == _endpoint_codenames()[endpoint]


@pytest.mark.parametrize("tool", sorted(TOOLS_WITHOUT_A_CODENAME))
def test_a_deliberately_bare_tool_stays_bare(tool):
    """Its endpoint names nothing, so naming something here would withhold it."""
    assert tool in _declared_tools()
    assert tool not in _tool_codenames()


def test_page_types_says_open_rather_than_saying_nothing():
    """The decision taken with the user, stated where it can be checked.

    A catalogue derived from installed code has no rows and no permission to
    name. (One backed by rows does, and ``locales`` is that case — it lands
    with the rest of the annotation pass.)

    But "no codename" is not the same as "no annotation", and asserting the
    absence of a codename would pass for both. A bare endpoint keeps the
    API-wide default and is closed to every scoped token, so ``page-types``
    carries ``authenticated()`` to say it is open on purpose — and *that* is
    what this checks, because its tool is bare and would otherwise be
    offered to a credential the door then turned away.
    """
    source = (_API / "page_types.py").read_text()
    assert "auth=authenticated()" in source
    assert "list_page_types" not in _endpoint_codenames()
    assert "phoxtail_page_types_list" not in _tool_codenames()


def test_nothing_else_is_bare_by_accident():
    """Every served cms endpoint either names a codename, is still owed, or
    declares ``authenticated()`` deliberately.

    The category this closes is the silent one: an endpoint that declares
    nothing looks identical to one nobody has reached yet, and both are
    invisible to a suite that only ever authenticates with a session.
    """
    deliberately_open = set()
    for path in _API.glob("*.py"):
        source = path.read_text()
        for match in re.finditer(r"auth=authenticated\(\),?\n\)\ndef (\w+)\(", source):
            deliberately_open.add(match.group(1))
    assert deliberately_open == ENDPOINTS_WITHOUT_A_CODENAME


def test_every_codename_is_a_real_permission(db):
    """A typo would refuse everyone, silently and forever."""
    from django.contrib.auth.models import Permission

    real = {f"{p.content_type.app_label}.{p.codename}" for p in Permission.objects.select_related("content_type")}
    assert _flatten(_endpoint_codenames().values()) <= real
    assert _flatten(_tool_codenames().values()) <= real
