"""Tests for the cross-project MCP tools in phoxtail.mcp.peers.

The tools are exercised as the plain functions the ``@mcp_server.tool``
decorator returns, with peer resolution and the remote MCP session patched
— no network, no docker, no sibling server.
"""

import asyncio
import json
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import patch

from phoxtail.cli.utils.net import Peer, UnknownPeer
from phoxtail.mcp.peers import peer_call, peer_list, peer_tools


def _run(coro):
    return asyncio.run(coro)


INVOICES = Peer("invoices-site", None, True)


def _text_result(text, is_error=False):
    return SimpleNamespace(
        content=[SimpleNamespace(text=text)],
        isError=is_error,
        structuredContent=None,
    )


class _FakeSession:
    """Stands in for a ClientSession against a peer's MCP server."""

    def __init__(self, call_result=None, tools=(), raises=None):
        self.call_result = call_result or _text_result("{}")
        self.tools = list(tools)
        self.raises = raises
        self.seen_call = None

    async def call_tool(self, name, arguments):
        if self.raises is not None:
            raise self.raises
        self.seen_call = (name, arguments)
        return self.call_result

    async def list_tools(self):
        if self.raises is not None:
            raise self.raises
        return SimpleNamespace(tools=self.tools)


def _session_patch(session):
    @asynccontextmanager
    async def fake_peer_session(peer):
        fake_peer_session.seen_peer = peer
        yield session

    fake_peer_session.seen_peer = None
    return patch("phoxtail.mcp.peers._peer_session", fake_peer_session)


class TestPeerCall:
    def test_runs_the_tool_on_the_peer(self):
        session = _FakeSession(call_result=_text_result('{"invoices": 3}'))
        with (
            patch("phoxtail.mcp.peers.resolve_peer", return_value=INVOICES),
            _session_patch(session),
        ):
            out = _run(peer_call(peer="invoices-site", tool="phoxtail_invoices_list", arguments={"limit": 5}))

        assert out == '{"invoices": 3}'
        assert session.seen_call == ("phoxtail_invoices_list", {"limit": 5})

    def test_unknown_peer_is_refused_before_any_connection(self):
        """The guard against reaching ourselves via the loopback fallback."""
        session = _FakeSession()
        with (
            patch(
                "phoxtail.mcp.peers.resolve_peer",
                side_effect=UnknownPeer("No project named 'invoice-site' … Attached peers: invoices-site."),
            ),
            _session_patch(session),
        ):
            out = _run(peer_call(peer="invoice-site", tool="t"))

        assert "invoices-site" in json.loads(out)["error"]
        assert session.seen_call is None, "connected despite an unknown peer"

    def test_discovery_failure_is_returned_as_json_not_raised(self):
        with patch("phoxtail.mcp.peers.resolve_peer", side_effect=OSError("no such file or directory: 'docker'")):
            out = _run(peer_call(peer="invoices-site", tool="t"))
        assert "docker" in json.loads(out)["error"]

    def test_unreachable_peer_server_is_returned_as_json(self):
        with (
            patch("phoxtail.mcp.peers.resolve_peer", return_value=INVOICES),
            _session_patch(_FakeSession(raises=ConnectionError("refused"))),
        ):
            out = _run(peer_call(peer="invoices-site", tool="t"))
        error = json.loads(out)["error"]
        assert "refused" in error
        assert "invoices-site" in error

    def test_peer_tools_cannot_be_chained(self):
        """Checked before anything else — no cross-project relay loops."""
        for name in ("phoxtail_peer_call", "phoxtail_peer_tools", "phoxtail_peer_list"):
            out = _run(peer_call(peer="invoices-site", tool=name))
            assert "chained" in json.loads(out)["error"]

    def test_refuses_to_relay_to_this_project_itself(self):
        """Self is attached too, so resolve_peer would happily route the
        call through our own MCP server — a pointless round trip. The
        error steers the model to the direct tool instead."""
        session = _FakeSession()
        with (
            patch("phoxtail.mcp.peers._current_slug", return_value="me"),
            patch("phoxtail.mcp.peers.resolve_peer", return_value=Peer("me", None, True)),
            _session_patch(session),
        ):
            out = _run(peer_call(peer="me", tool="phoxtail_blocks_list"))
        error = json.loads(out)["error"]
        assert "this project" in error
        assert "phoxtail_blocks_list" in error
        assert session.seen_call is None

    def test_defaults_arguments_to_empty(self):
        session = _FakeSession()
        with (
            patch("phoxtail.mcp.peers.resolve_peer", return_value=INVOICES),
            _session_patch(session),
        ):
            _run(peer_call(peer="invoices-site", tool="t"))
        assert session.seen_call == ("t", {})

    def test_peer_reported_error_becomes_error_json(self):
        """The peer validates the tool name — its refusal must reach the
        model as an error, not as an ordinary-looking result string."""
        session = _FakeSession(call_result=_text_result("Unknown tool: made_up_tool", is_error=True))
        with (
            patch("phoxtail.mcp.peers.resolve_peer", return_value=INVOICES),
            _session_patch(session),
        ):
            out = _run(peer_call(peer="invoices-site", tool="made_up_tool"))
        assert "made_up_tool" in json.loads(out)["error"]


class TestPeerTools:
    def test_lists_the_peers_tools_first_lines_only(self):
        tools = [
            SimpleNamespace(name="phoxtail_invoices_list", description="List invoices.\n\nLong schema details…"),
            SimpleNamespace(name="phoxtail_blocks_list", description=None),
            SimpleNamespace(name="phoxtail_peer_call", description="Should be hidden — no relaying."),
        ]
        with (
            patch("phoxtail.mcp.peers.resolve_peer", return_value=INVOICES),
            _session_patch(_FakeSession(tools=tools)),
        ):
            out = json.loads(_run(peer_tools(peer="invoices-site")))

        assert {t["name"] for t in out} == {"phoxtail_invoices_list", "phoxtail_blocks_list"}
        by_name = {t["name"]: t["description"] for t in out}
        assert by_name["phoxtail_invoices_list"] == "List invoices."
        assert by_name["phoxtail_blocks_list"] == ""

    def test_search_filters_by_name_or_description(self):
        """A peer can offer 150+ tools; a filtered ask keeps the reply small
        enough to stay inline in the caller's transcript."""
        tools = [
            SimpleNamespace(name="phoxtail_invoices_list", description="List invoices."),
            SimpleNamespace(name="phoxtail_blocks_list", description="List stream blocks."),
            SimpleNamespace(name="phoxtail_parties_list", description="List invoice parties."),
        ]
        with (
            patch("phoxtail.mcp.peers.resolve_peer", return_value=INVOICES),
            _session_patch(_FakeSession(tools=tools)),
        ):
            out = json.loads(_run(peer_tools(peer="invoices-site", search="invoice")))

        assert {t["name"] for t in out} == {"phoxtail_invoices_list", "phoxtail_parties_list"}

    def test_tolerates_blank_and_whitespace_descriptions(self):
        """A description of ' ' strips to nothing — the catalogue must not
        crash on one oddly-authored tool."""
        tools = [
            SimpleNamespace(name="phoxtail_a", description="   "),
            SimpleNamespace(name="phoxtail_b", description="\n\nSecond line only after blanks."),
        ]
        with (
            patch("phoxtail.mcp.peers.resolve_peer", return_value=INVOICES),
            _session_patch(_FakeSession(tools=tools)),
        ):
            out = json.loads(_run(peer_tools(peer="invoices-site")))
        by_name = {t["name"]: t["description"] for t in out}
        assert by_name["phoxtail_a"] == ""
        assert by_name["phoxtail_b"] == "Second line only after blanks."

    def test_unknown_peer_is_refused(self):
        with patch("phoxtail.mcp.peers.resolve_peer", side_effect=UnknownPeer("Attached peers: invoices-site.")):
            out = _run(peer_tools(peer="invoice-site"))
        assert "invoices-site" in json.loads(out)["error"]

    def test_unreachable_peer_server_is_returned_as_json(self):
        with (
            patch("phoxtail.mcp.peers.resolve_peer", return_value=INVOICES),
            _session_patch(_FakeSession(raises=ConnectionError("refused"))),
        ):
            out = _run(peer_tools(peer="invoices-site"))
        assert "refused" in json.loads(out)["error"]


class TestPeerList:
    def test_lists_siblings_excluding_this_project(self):
        peers = [
            Peer("invoices-site", None, True),
            Peer("registry-site", None, False),
            Peer("me", None, True),
        ]
        with (
            patch("phoxtail.mcp.peers.list_peers", return_value=peers),
            patch("phoxtail.mcp.peers._current_slug", return_value="me"),
        ):
            out = json.loads(peer_list())

        assert {p["peer"] for p in out} == {"invoices-site", "registry-site"}
        assert {p["peer"]: p["running"] for p in out}["registry-site"] is False

    def test_empty_when_nothing_else_is_attached(self):
        with (
            patch("phoxtail.mcp.peers.list_peers", return_value=[Peer("me", None, True)]),
            patch("phoxtail.mcp.peers._current_slug", return_value="me"),
        ):
            assert json.loads(peer_list()) == []

    def test_discovery_failure_is_returned_as_json_not_raised(self):
        with patch("phoxtail.mcp.peers.list_peers", side_effect=OSError("boom")):
            assert "boom" in json.loads(peer_list())["error"]


class TestRegisteredOnMcpServer:
    """Both consumer paths — MCP clients and the chatbot — read this registry."""

    def test_all_peer_tools_are_registered(self):
        from phoxtail.mcp import mcp_server

        registered = mcp_server._tool_manager._tools
        assert "phoxtail_peer_list" in registered
        assert "phoxtail_peer_tools" in registered
        assert "phoxtail_peer_call" in registered
