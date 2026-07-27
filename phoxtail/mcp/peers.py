"""MCP tools for cross-project ("peer") calls over the shared local net.

Peer tools are *clients* of the sibling project's own MCP server (the
`mcp` service every attached project runs). The named tool executes over
there, in the peer's environment — with the peer's installed packages and
therefore the peer's full vocabulary, including contributed tools this
project has never heard of. Only the conversation travels.

Deliberately a handful of tools rather than a `peer` argument on every
registered tool: threading it through every schema would advertise
cross-project *writes* on tools like ``phoxtail_pages_publish`` and cost
tokens on every request. Keeping the concept in one place also keeps the
guard in one place.
"""

from __future__ import annotations

import json
from contextlib import asynccontextmanager

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from phoxtail.cli.utils.net import Peer, UnknownPeer, list_peers, resolve_peer
from phoxtail.mcp import mcp_server
from phoxtail.mcp._http import outbound_token

PEER_TOOL_PREFIX = "phoxtail_peer_"


def _current_slug() -> str | None:
    from phoxtail.cli.utils.config import get_project_name, slugify

    try:
        return slugify(get_project_name())
    except Exception:
        return None


@asynccontextmanager
async def _peer_session(peer: Peer):
    """An initialized MCP session against *peer*'s server.

    Over HTTP, the Bearer sent is whatever the caller who invoked this
    tool forwarded — never this machine's own stored token for the peer.
    An unauthenticated caller reaching this server over the network must
    not be able to borrow the operator's identity against a *third*
    project just because this server happens to have a token for it.
    Over stdio there is no caller to forward, so the stored token for the
    peer's canonical web address is used, same as any other CLI call —
    one ``phoxtail auth login`` against the peer is the entire onboarding.
    """
    token = outbound_token(peer.address)
    headers = {"Authorization": f"Bearer {token}"} if token else None
    async with streamablehttp_client(peer.mcp_url, headers=headers) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session


@mcp_server.tool(
    name="phoxtail_peer_list",
    description=(
        "List the sibling Phoxtail projects attached to this machine's shared "
        "local net — the valid values for the `peer` argument of "
        "phoxtail_peer_tools and phoxtail_peer_call. Each entry reports "
        "whether the peer is currently running; a stopped peer cannot answer."
    ),
)
def peer_list() -> str:
    try:
        current = _current_slug()
        return json.dumps([{"peer": p.slug, "running": p.running} for p in list_peers() if p.slug != current])
    except Exception as exc:
        return json.dumps({"error": f"Peer discovery failed: {exc}"})


@mcp_server.tool(
    name="phoxtail_peer_tools",
    description=(
        "List the tools a sibling project's own MCP server offers. Peers can "
        "expose tools this project does not have (e.g. an app installed only "
        "there), so consult this before assuming a capability is missing — "
        "and to get the exact tool names phoxtail_peer_call expects. Pass "
        "`search` to filter by substring of name or description (e.g. "
        "'invoice') instead of reading the full catalogue."
    ),
)
async def peer_tools(peer: str, search: str | None = None) -> str:
    try:
        target = resolve_peer(peer)
    except UnknownPeer as exc:
        return json.dumps({"error": str(exc)})
    except Exception as exc:
        return json.dumps({"error": f"Peer discovery failed: {exc}"})

    try:
        async with _peer_session(target) as session:
            listed = await session.list_tools()
    except Exception as exc:
        return json.dumps({"error": f"Could not reach {peer}'s MCP server: {exc}"})

    # First line of each description: enough to choose a tool without
    # paying for every peer's full schema catalogue on one turn.
    catalogue = [
        {"name": t.name, "description": ((t.description or "").strip().splitlines() or [""])[0]}
        for t in listed.tools
        if not t.name.startswith(PEER_TOOL_PREFIX)
    ]
    if search:
        needle = search.lower()
        catalogue = [t for t in catalogue if needle in t["name"].lower() or needle in t["description"].lower()]
    return json.dumps(catalogue)


@mcp_server.tool(
    name="phoxtail_peer_call",
    description=(
        "Run a tool belonging to a *sibling project* on this machine, on that "
        "project's own server. Use it to read or write data belonging to a "
        "different project — e.g. list blocks in a sibling site to copy a "
        "design. `peer` is a project slug; call phoxtail_peer_list first if "
        "unsure, and never guess it. `tool` is a tool name from "
        "phoxtail_peer_tools — the peer may offer tools this project does "
        "not have. `arguments` is the JSON object that tool expects. Only "
        "use this when the user asks about a *different* project — for the "
        "current project, call the tool directly."
    ),
)
async def peer_call(peer: str, tool: str, arguments: dict | None = None) -> str:
    """Run *tool* on *peer*'s MCP server — the one cross-project entry point.

    The peer slug is validated before anything is sent: a wrong slug would
    otherwise resolve to loopback and reach this project instead (see
    ``resolve_peer``). The tool name is validated by the peer, the only
    side that knows its own registry. Errors name the valid values so the
    model can correct itself rather than retrying blindly.
    """
    if tool.startswith(PEER_TOOL_PREFIX):
        return json.dumps(
            {"error": "Peer tools cannot be chained through a peer — address the target project directly."}
        )
    if peer and peer.strip() == _current_slug():
        return json.dumps({"error": f"{peer.strip()!r} is this project — call {tool} directly instead of relaying it."})

    try:
        target = resolve_peer(peer)
    except UnknownPeer as exc:
        return json.dumps({"error": str(exc)})
    except Exception as exc:
        return json.dumps({"error": f"Peer discovery failed: {exc}"})

    try:
        async with _peer_session(target) as session:
            result = await session.call_tool(tool, arguments or {})
    except Exception as exc:
        return json.dumps({"error": f"{tool} against {peer}: {exc}"})

    text = "\n".join(block.text for block in result.content if getattr(block, "text", None))
    if result.isError:
        return json.dumps({"error": text or f"{tool} failed on {peer}."})
    return text or json.dumps(result.structuredContent or {})
