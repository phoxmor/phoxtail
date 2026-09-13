"""Each streams tool names the codename its endpoint already names.

The endpoint decides; the tool only repeats the decision, so that a narrowed
credential is offered a catalogue matching the doors that will actually open.
If the two ever disagree the failure is quiet in both directions.

Not every tool is here, and the absences are decisions rather than gaps:

- the five ``sessions`` tools carry ``local_only`` and no scope — they write
  to this server's own disk and hand back paths, which name nothing a remote
  caller can open;
- ``render_block``, ``screenshot_page`` and ``capture_variant_previews``
  reach the site rather than this app's API, and land in their own commit;
- ``get_context`` reads across into the design app, and lands with them.

``ENDPOINTS_WITHOUT_A_CODENAME`` names the two endpoints that deliberately
declare nothing, so that "everything is annotated" can still be asserted.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_API = Path(__file__).resolve().parent.parent / "api" / "v1"
_MCP = Path(__file__).resolve().parent.parent / "mcp"

# Tool name -> the endpoint function whose act it performs.
PAIRS = {
    "phoxtail_studio_list_blocks": "list_blocks",
    "phoxtail_studio_get_block": "get_block_by_id",
    "phoxtail_studio_create_block": "create_block",
    "phoxtail_studio_update_block": "update_block_by_id",
    "phoxtail_studio_delete_block": "delete_block",
    "phoxtail_studio_list_block_categories": "list_block_categories",
    "phoxtail_studio_get_block_category": "get_block_category",
    "phoxtail_studio_create_block_category": "create_block_category",
    "phoxtail_studio_update_block_category": "update_block_category",
    "phoxtail_studio_delete_block_category": "delete_block_category",
    "phoxtail_studio_set_block_categories": "set_block_categories",
    "phoxtail_studio_add_block_category": "add_block_category",
    "phoxtail_studio_remove_block_category": "remove_block_category",
    "phoxtail_studio_list_collections": "list_collections",
    "phoxtail_studio_get_collection": "get_collection_by_id",
    "phoxtail_studio_create_collection": "create_collection",
    "phoxtail_studio_update_collection": "update_collection_by_id",
    "phoxtail_studio_delete_collection": "delete_collection",
    "phoxtail_studio_list_shared_blocks": "list_shared_blocks",
    "phoxtail_studio_get_shared_block": "get_shared_block_by_id",
    "phoxtail_studio_create_shared_block": "create_shared_block",
    "phoxtail_studio_update_shared_block": "update_shared_block_by_id",
    "phoxtail_studio_delete_shared_block": "delete_shared_block_by_id",
    "phoxtail_studio_list_variants": "list_variants",
    "phoxtail_studio_get_variant": "get_variant_by_id",
    "phoxtail_studio_create_variant": "create_variant",
    "phoxtail_studio_update_variant": "update_variant_by_id",
    "phoxtail_studio_delete_variant": "delete_variant",
    # Names two codenames, and so does its endpoint — the tuples must match
    # in order as well as in content, which is what pins them together.
    "phoxtail_studio_get_context": "get_context",
}

# Tools with no endpoint of their own. Each names what it actually reads or
# reaches, which is why none of them is simply left bare: an MCP tool naming
# no codename is offered to *every* credential, including one narrowed to a
# single unrelated act — the opposite of the API's default, where declaring
# nothing closes the door.
TOOLS_WITHOUT_AN_ENDPOINT = {
    # Reads a variant and compares it against local files.
    "phoxtail_studio_diff_variant": ("phoxtail_streams.view_blockvariant",),
    # An orchestrator: reads the variant and its block, then returns a
    # playbook naming the tools to call. It writes nothing itself, and every
    # step it recommends is guarded on its own.
    "phoxtail_studio_capture_variant_previews": (
        "phoxtail_streams.view_blockvariant",
        "phoxtail_streams.view_block",
    ),
    # These drive a headless browser at the agent app's screenshot view,
    # which asks the person for access_chatbot. Naming the same codename is
    # the tool mirroring what it reaches, across an app boundary — the same
    # thing media does with Wagtail's codenames.
    "phoxtail_studio_render_block": ("phoxtail_agent.access_chatbot",),
    "phoxtail_studio_screenshot_page": ("phoxtail_agent.access_chatbot",),
}

# Endpoints that deliberately declare no codename — see the class in
# ``api/tests/test_auth.py`` for why, and note that declaring nothing leaves
# a door closed to scoped tokens rather than open.
ENDPOINTS_WITHOUT_A_CODENAME = {"schema_catalog", "list_page_type_app_labels"}


def _endpoint_codenames() -> dict[str, str | tuple[str, ...]]:
    """``{view function: codename}`` for every guarded streams endpoint.

    An endpoint naming several codenames yields a tuple of them. Only
    ``push_variant`` does, and it does so because its envelope writes three
    models — see the annotation for why all six are required.
    """
    found: dict[str, str | tuple[str, ...]] = {}
    for path in _API.glob("*.py"):
        source = path.read_text()
        for match in re.finditer(r"auth=guarded\(\s*((?:\s*\"[^\"]+\",?\s*)+)\),?\n\)\ndef (\w+)\(", source):
            names = tuple(re.findall(r"\"([^\"]+)\"", match.group(1)))
            found[match.group(2)] = names[0] if len(names) == 1 else names
    return found


def _tool_codenames() -> dict[str, str | tuple[str, ...]]:
    """``{tool name: codename}`` for every scoped streams tool.

    A tool naming several codenames yields a tuple of them, matching
    :func:`_endpoint_codenames`.
    """
    found: dict[str, str | tuple[str, ...]] = {}
    for path in _MCP.glob("*.py"):
        source = path.read_text()
        for match in re.finditer(r'name="(\w+)",\n\s+auth=\[scoped\(((?:\s*"[^"]+",?\s*)+)\)\]', source):
            names = tuple(re.findall(r'"([^"]+)"', match.group(2)))
            found[match.group(1)] = names[0] if len(names) == 1 else names
    return found


def _all_endpoint_codenames() -> set[str]:
    """Every codename any endpoint names, flattened.

    ``push_variant`` names six, so the values are not all strings.
    """
    flat: set[str] = set()
    for value in _endpoint_codenames().values():
        flat.update((value,) if isinstance(value, str) else value)
    return flat


def _all_tool_codenames() -> set[str]:
    """Every codename any tool names, flattened across apps."""
    flat: set[str] = set()
    for value in _tool_codenames().values():
        flat.update((value,) if isinstance(value, str) else value)
    return flat


def test_every_endpoint_is_accounted_for():
    """Annotated, or deliberately not.

    An endpoint that is neither is the hole this pass closes. Nothing is
    pending any more: the set that held the deferrals is gone, and so is the
    test that refused to let it be forgotten.
    """
    from phoxtail.api import api

    api.urls  # force the routers to build
    served = {
        op.view_func.__name__
        for prefix, router in api._routers
        if prefix.startswith("streams")
        for view in router.path_operations.values()
        for op in view.operations
    }
    unaccounted = served - set(_endpoint_codenames()) - ENDPOINTS_WITHOUT_A_CODENAME
    assert unaccounted == set()


def test_every_tool_is_scoped():
    assert sorted(_tool_codenames()) == sorted({**PAIRS, **TOOLS_WITHOUT_AN_ENDPOINT})


@pytest.mark.parametrize("tool,endpoint", sorted(PAIRS.items()))
def test_the_tool_names_what_its_endpoint_names(tool, endpoint):
    assert _tool_codenames()[tool] == _endpoint_codenames()[endpoint]


@pytest.mark.parametrize("tool,codenames", sorted(TOOLS_WITHOUT_AN_ENDPOINT.items()))
def test_a_tool_without_an_endpoint_names_what_it_reaches(tool, codenames):
    found = _tool_codenames()[tool]
    # Parenthesised deliberately: without them Python reads this as
    # ``(found,) if ... else (found == codenames)``, and a single-codename
    # tool would assert a non-empty tuple — always true, never a test.
    assert ((found,) if isinstance(found, str) else found) == codenames


def test_categorising_a_block_names_the_block(db):
    """The decision taken with the user, stated where it can be checked.

    Putting a block in a category changes the *block*; the category is only
    referenced. Django has no implicit rule that referencing a row needs
    permission over it, and ``BlockCategory`` has no ``choose`` permission
    to ask for — so asking for one would invent the rule rather than follow
    it.
    """
    codenames = _endpoint_codenames()
    for endpoint in ("set_block_categories", "add_block_category", "remove_block_category"):
        assert codenames[endpoint] == "phoxtail_streams.change_block", endpoint
    assert codenames["list_block_categories_for_block"] == "phoxtail_streams.view_block"


def test_every_codename_is_a_real_permission(db):
    """A typo would refuse everyone, silently and forever."""
    from django.contrib.auth.models import Permission

    real = {
        f"phoxtail_streams.{p.codename}" for p in Permission.objects.filter(content_type__app_label="phoxtail_streams")
    }
    assert {c for c in _all_tool_codenames() if c.startswith("phoxtail_streams.")} <= real
    assert _all_endpoint_codenames() <= real
