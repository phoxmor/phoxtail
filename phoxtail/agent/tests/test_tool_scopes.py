"""Each agent tool names the codename its endpoint already names.

The endpoint decides; the tool only repeats the decision, so that a narrowed
credential is offered a catalogue matching the doors that will actually open.
If the two ever disagree the failure is quiet in both directions — a tool
offered and then refused, or one withheld that would have worked — so the
agreement is worth a test rather than care.

Pinned by reading the annotations rather than by calling anything: what is at
stake is two strings being equal, and the surest way to check that is to read
both.

Chat is not here. Its two endpoints are browser-only and have no tools, so
there is nothing to pair — see ``api/tests/test_auth.py`` for why they must
stay unannotated.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_API = Path(__file__).resolve().parent.parent / "api" / "v1"
_MCP = Path(__file__).resolve().parent.parent / "mcp"

# Tool name -> the endpoint function whose act it performs. Written out rather
# than derived: the names are close enough to tempt a rule, and a rule would
# quietly pair the wrong two the first time one is renamed.
PAIRS = {
    "phoxtail_agent_list_providers": "list_providers",
    "phoxtail_agent_get_provider": "get_provider",
    "phoxtail_agent_create_provider": "create_provider",
    "phoxtail_agent_update_provider": "update_provider",
    "phoxtail_agent_delete_provider": "delete_provider",
    "phoxtail_agent_list_artifacts": "list_artifacts",
    "phoxtail_agent_get_artifact": "get_artifact",
    "phoxtail_agent_create_artifact": "create_artifact",
    "phoxtail_agent_update_artifact": "update_artifact",
    "phoxtail_agent_delete_artifact": "delete_artifact",
    "phoxtail_agent_get_settings": "get_agent_settings",
    "phoxtail_agent_update_settings": "update_agent_settings",
}


def _endpoint_codenames() -> dict[str, str]:
    """``{view function: codename}`` for every guarded agent endpoint."""
    found = {}
    for path in _API.glob("*.py"):
        source = path.read_text()
        for match in re.finditer(r'auth=guarded\("([^"]+)"\),\n\)\ndef (\w+)\(', source):
            found[match.group(2)] = match.group(1)
    return found


def _tool_codenames() -> dict[str, str]:
    """``{tool name: codename}`` for every scoped agent tool."""
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

    real = {f"phoxtail_agent.{p.codename}" for p in Permission.objects.filter(content_type__app_label="phoxtail_agent")}
    assert set(_tool_codenames().values()) <= real
    assert set(_endpoint_codenames().values()) <= real
