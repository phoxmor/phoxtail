"""Each users tool names the codename its endpoint already names.

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
# than derived: the names are close enough to tempt a rule, and a rule would
# quietly pair the wrong two the first time one is renamed.
PAIRS = {
    "phoxtail_users_list_users": "list_users",
    "phoxtail_users_get_user": "get_user",
    "phoxtail_users_create_user": "create_user",
    "phoxtail_users_bulk_create_users": "bulk_create_users",
    "phoxtail_users_update_user": "update_user",
    "phoxtail_users_verify_email": "verify_email",
    "phoxtail_users_bulk_verify_emails": "bulk_verify_emails",
    "phoxtail_users_delete_user": "delete_user",
    "phoxtail_users_list_genders": "list_genders",
    "phoxtail_users_get_gender": "get_gender",
    "phoxtail_users_create_gender": "create_gender",
    "phoxtail_users_update_gender": "update_gender",
    "phoxtail_users_delete_gender": "delete_gender",
}


def _endpoint_codenames() -> dict[str, str]:
    """``{view function: codename}`` for every guarded users endpoint."""
    found = {}
    for path in _API.glob("*.py"):
        source = path.read_text()
        for match in re.finditer(r'auth=guarded\("([^"]+)"\),\n\)\ndef (\w+)\(', source):
            found[match.group(2)] = match.group(1)
    return found


def _tool_codenames() -> dict[str, str]:
    """``{tool name: codename}`` for every scoped users tool."""
    found = {}
    for path in _MCP.glob("*.py"):
        source = path.read_text()
        for match in re.finditer(r'name="(phoxtail_users_\w+)",\n\s+auth=\[scoped\("([^"]+)"\)\]', source):
            found[match.group(1)] = match.group(2)
    return found


def test_every_endpoint_is_guarded():
    """A missing annotation is the hole this pass exists to close."""
    assert len(_endpoint_codenames()) == len(PAIRS)


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

    real = {f"phoxtail_users.{p.codename}" for p in Permission.objects.filter(content_type__app_label="phoxtail_users")}
    assert set(_tool_codenames().values()) <= real
    assert set(_endpoint_codenames().values()) <= real
