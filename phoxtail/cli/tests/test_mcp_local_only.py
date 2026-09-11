"""The session tools are offered only where their paths mean something.

``phoxtail_studio_open_variant`` and its four siblings write files to the
MCP server's own disk and hand back the paths. Reached over HTTP the agent
is elsewhere and those paths open nothing — and the tool does not fail
saying so, it succeeds and returns them. So they are withheld from a
caller who arrived over the network.

What is asserted here is the *registry's* behaviour, not a predicate's.
fastmcp runs a component's ``auth`` checks inside ``list_tools`` and
``get_tool``, which is what makes both moments impossible to skip: a
shorter catalogue is only economy, and a caller who knows a name would
otherwise call it anyway.
"""

from __future__ import annotations

import asyncio
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import patch

from phoxtail.mcp import mcp_server
from phoxtail.mcp.authorization import local_only

SESSION_TOOLS = {
    "phoxtail_studio_open_variant",
    "phoxtail_studio_commit_variant",
    "phoxtail_studio_discard_variant",
    "phoxtail_studio_list_sessions",
    "phoxtail_studio_refresh_session",
}

# Equally unusable from a distance, and deliberately not guarded: their
# question is about an argument, not about the caller. They fail honestly
# on a path that does not exist, where the session tools succeed and lie.
UPLOAD_TOOLS = {
    "phoxtail_images_upload",
    "phoxtail_documents_upload",
    "phoxtail_videos_upload",
    "phoxtail_audio_upload",
}


@contextmanager
def _over_http():
    """Serve as if an inbound HTTP request were in flight.

    Stubs the same lookup ``test_mcp_http_identity`` stubs, for the same
    reason: that fastmcp populates it over streamable-http and not over
    stdio is a property of the library, verified against both real
    transports rather than re-asserted here.
    """
    with patch("phoxtail.mcp._http._inbound_http_request", return_value=SimpleNamespace(headers={})):
        yield


class TestTheCheck:
    def test_permits_a_caller_who_arrived_over_no_network(self):
        """stdio, and the in-process chatbot, share this machine."""
        assert local_only(None) is True

    def test_refuses_a_caller_who_arrived_over_http(self):
        with _over_http():
            assert local_only(None) is False

    def test_identity_does_not_enter_it(self):
        """A superuser on a phone is as far away as anyone else."""
        with _over_http():
            admin = SimpleNamespace(token=SimpleNamespace(scopes=[], claims={"is_superuser": True}))
            assert local_only(admin) is False


class TestTheCatalogue:
    def test_session_tools_are_offered_locally(self):
        listed = {t.name for t in asyncio.run(mcp_server.list_tools())}
        assert SESSION_TOOLS <= listed

    def test_session_tools_are_withheld_over_http(self):
        with _over_http():
            listed = {t.name for t in asyncio.run(mcp_server.list_tools())}
        assert not (SESSION_TOOLS & listed)

    def test_nothing_else_is_withheld_over_http(self):
        """The guard is on five tools, and the catalogue proves it."""
        local = {t.name for t in asyncio.run(mcp_server.list_tools())}
        with _over_http():
            remote = {t.name for t in asyncio.run(mcp_server.list_tools())}
        assert local - remote == SESSION_TOOLS

    def test_the_upload_tools_keep_their_place(self):
        with _over_http():
            listed = {t.name for t in asyncio.run(mcp_server.list_tools())}
        assert UPLOAD_TOOLS <= listed


class TestCallingByName:
    """Hiding is not securing: a name the caller already knows still fails."""

    def test_a_session_tool_does_not_resolve_over_http(self):
        with _over_http():
            tool = asyncio.run(mcp_server.get_tool("phoxtail_studio_open_variant"))
        assert tool is None

    def test_the_same_name_resolves_locally(self):
        tool = asyncio.run(mcp_server.get_tool("phoxtail_studio_open_variant"))
        assert tool is not None

    def test_an_unguarded_tool_resolves_over_http(self):
        with _over_http():
            tool = asyncio.run(mcp_server.get_tool("phoxtail_studio_list_blocks"))
        assert tool is not None
