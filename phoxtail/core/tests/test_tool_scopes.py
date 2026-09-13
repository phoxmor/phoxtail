"""Each core tool names the codename its endpoint already names.

The endpoint decides; the tool only repeats the decision, so that a narrowed
credential is offered a catalogue matching the doors that will actually open.
If the two ever disagree the failure is quiet in both directions — a tool
offered and then refused, or one withheld that would have worked — so the
agreement is worth a test rather than care.

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
# than derived: the tools still carry the `phoxtail_content_` prefix they were
# given before internal links moved into this app, so no rule over the names
# would pair them anyway.
PAIRS = {
    "phoxtail_content_list_internal_links": "list_internal_links",
    "phoxtail_content_get_internal_link": "get_internal_link",
    "phoxtail_content_create_internal_link": "create_internal_link",
    "phoxtail_content_update_internal_link": "update_internal_link",
    "phoxtail_content_delete_internal_link": "delete_internal_link",
}


def _endpoint_codenames() -> dict[str, str]:
    """``{view function: codename}`` for every guarded core endpoint."""
    found = {}
    for path in _API.glob("*.py"):
        source = path.read_text()
        for match in re.finditer(r'auth=guarded\("([^"]+)"\),\n\)\ndef (\w+)\(', source):
            found[match.group(2)] = match.group(1)
    return found


def _tool_codenames() -> dict[str, str]:
    """``{tool name: codename}`` for every scoped core tool."""
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


def test_every_codename_is_a_real_permission(db):
    """A typo would refuse everyone, silently and forever.

    Django creates these rows at ``migrate`` for every model, so the
    ``auth_permission`` table is the registry and nothing else has to be kept.
    """
    from django.contrib.auth.models import Permission

    real = {f"phoxtail_core.{p.codename}" for p in Permission.objects.filter(content_type__app_label="phoxtail_core")}
    assert set(_tool_codenames().values()) <= real
    assert set(_endpoint_codenames().values()) <= real
