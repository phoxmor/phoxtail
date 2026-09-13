"""Each media tool names the codename its endpoint already names.

The endpoint decides; the tool only repeats the decision, so that a narrowed
credential is offered a catalogue matching the doors that will actually open.
If the two ever disagree the failure is quiet in both directions — a tool
offered and then refused, or one withheld that would have worked.

This domain's endpoints carry ``scoped()`` rather than ``guarded()``, because
Wagtail grants file permissions per collection and the person's half is asked
inside the body. The credential's half is still one codename per act, and it
is that half this file pins.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_API = Path(__file__).resolve().parent.parent / "api" / "v1"
_MCP = Path(__file__).resolve().parent.parent / "mcp"

# Tool name -> the endpoint function whose act it performs. Written out
# rather than derived: the names do not agree at all — three prefixes for
# four resources, and two tools still carrying `phoxtail_pages_` from before
# this app existed — so no rule over them would pair the right two.
PAIRS = {
    "phoxtail_pages_list_images": "list_images",
    "phoxtail_images_get": "get_image",
    "phoxtail_images_view": "view_image",
    "phoxtail_images_upload": "upload_image",
    "phoxtail_images_update": "update_image",
    "phoxtail_images_delete": "delete_image",
    "phoxtail_pages_list_documents": "list_documents",
    "phoxtail_documents_get": "get_document",
    "phoxtail_documents_upload": "upload_document",
    "phoxtail_documents_update": "update_document",
    "phoxtail_documents_delete": "delete_document",
    "phoxtail_videos_list": "list_videos",
    "phoxtail_videos_get": "get_video",
    "phoxtail_videos_upload": "upload_video",
    "phoxtail_videos_update": "update_video",
    "phoxtail_videos_delete": "delete_video",
    "phoxtail_audio_list": "list_audio",
    "phoxtail_audio_get": "get_audio",
    "phoxtail_audio_upload": "upload_audio",
    "phoxtail_audio_update": "update_audio",
    "phoxtail_audio_delete": "delete_audio",
}


def _endpoint_codenames() -> dict[str, str]:
    """``{view function: codename}`` for every scoped media endpoint."""
    found = {}
    for path in _API.glob("*.py"):
        source = path.read_text()
        for match in re.finditer(r'auth=scoped\("([^"]+)"\),\n\)\ndef (\w+)\(', source):
            found[match.group(2)] = match.group(1)
    return found


def _tool_codenames() -> dict[str, str]:
    """``{tool name: codename}`` for every scoped media tool."""
    found = {}
    for path in _MCP.glob("*.py"):
        source = path.read_text()
        for match in re.finditer(r'name="(\w+)",\n\s+auth=\[scoped\("([^"]+)"\)\]', source):
            found[match.group(1)] = match.group(2)
    return found


def test_every_endpoint_is_scoped():
    """A missing annotation is the hole this pass exists to close."""
    assert sorted(_endpoint_codenames()) == sorted(PAIRS.values())


def test_every_tool_is_scoped():
    assert sorted(_tool_codenames()) == sorted(PAIRS)


@pytest.mark.parametrize("tool,endpoint", sorted(PAIRS.items()))
def test_the_tool_names_what_its_endpoint_names(tool, endpoint):
    assert _tool_codenames()[tool] == _endpoint_codenames()[endpoint]


def test_every_codename_is_a_real_permission(db):
    """A typo would refuse everyone, silently and forever.

    The labels here are Wagtail's own — ``wagtailimages``, ``wagtaildocs``,
    ``wagtailmedia`` — not ``phoxtail_media``. Our models are swapped in, but
    each policy pins its ``auth_model`` to Wagtail's, so the permissions live
    under those labels and a ``phoxtail_media.*`` codename would name a row
    nothing grants and nothing checks.
    """
    from django.contrib.auth.models import Permission

    real = {
        f"{p.content_type.app_label}.{p.codename}"
        for p in Permission.objects.filter(content_type__app_label__in=["wagtailimages", "wagtaildocs", "wagtailmedia"])
    }
    assert set(_tool_codenames().values()) <= real
    assert set(_endpoint_codenames().values()) <= real
