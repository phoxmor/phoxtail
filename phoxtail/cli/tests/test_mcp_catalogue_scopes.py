"""A scoped credential is offered only the tools its scopes cover.

``test_mcp_scoped`` asks whether the check answers correctly. This asks
the question after it: whether anything runs the check. Those are not the
same fact — a correct predicate nobody consults filters nothing, and the
failure is silent, because a catalogue that was never narrowed looks
exactly like one whose caller was entitled to all of it.

Built on a throwaway server rather than on a domain's real tools. The
registry runs a component's checks the same way for all of them, so the
mechanism is what is worth pinning down, and the assertion does not move
every time a domain is annotated.

Note the third tool. A tool that declares nothing stays visible to a
narrowed credential — the opposite of the API, where the shared default
refuses a scoped token everywhere unannotated. Tools filter for economy
and enforcement lives at the endpoint, so the safe direction differs on
each side, and that is deliberate rather than an oversight.
"""

from __future__ import annotations

import asyncio
from contextlib import contextmanager
from unittest.mock import patch

import pytest
from fastmcp import FastMCP
from fastmcp.server.auth import AccessToken

from phoxtail.mcp.authorization import scoped

READ = "phoxtail_dashboard.view_menu"
DELETE = "phoxtail_dashboard.delete_menu"


@contextmanager
def _presenting(*scopes, unrestricted=False):
    """Serve as if this credential had arrived over HTTP.

    The transport matters as much as the token: fastmcp skips every
    component check when the current transport is stdio, so a listing
    taken outside a transport would be filtered while a local session
    is not.
    """
    from fastmcp.server.context import _current_transport

    token = AccessToken(
        token="opaque",
        client_id="tester",
        scopes=list(scopes),
        claims={"unrestricted": unrestricted},
    )
    transport = _current_transport.set("http")
    try:
        with patch("fastmcp.server.dependencies.get_access_token", return_value=token):
            yield
    finally:
        _current_transport.reset(transport)


@pytest.fixture(scope="module")
def server():
    server = FastMCP("catalogue-under-test")

    @server.tool(name="reader", auth=[scoped(READ)])
    def reader() -> str:
        return "read"

    @server.tool(name="deleter", auth=[scoped(DELETE)])
    def deleter() -> str:
        return "deleted"

    @server.tool(name="unannotated")
    def unannotated() -> str:
        return "anyone"

    return server


def _catalogue(server):
    return {tool.name for tool in asyncio.run(server.list_tools())}


def test_a_narrowed_credential_sees_only_what_it_may_use(server):
    with _presenting(READ):
        assert _catalogue(server) == {"reader", "unannotated"}


def test_widening_the_credential_widens_the_catalogue(server):
    with _presenting(READ, DELETE):
        assert _catalogue(server) == {"reader", "deleter", "unannotated"}


def test_an_unrestricted_credential_sees_everything(server):
    """It brought no ceiling, so there is nothing to filter against."""
    with _presenting(unrestricted=True):
        assert _catalogue(server) == {"reader", "deleter", "unannotated"}


def test_a_credential_naming_nothing_sees_only_the_unannotated(server):
    with _presenting():
        assert _catalogue(server) == {"unannotated"}


def test_a_local_session_is_filtered_by_nothing(server):
    """The canary for fastmcp skipping component checks on stdio.

    Every tool phoxtail annotates would vanish from local sessions if a
    future version stopped doing this — roughly a hundred and fifty of
    them, with no error anywhere. A person would find that, not a test,
    unless this one fails first and says why.
    """
    from fastmcp.server.context import _current_transport

    transport = _current_transport.set("stdio")
    try:
        assert _catalogue(server) == {"reader", "deleter", "unannotated"}
    finally:
        _current_transport.reset(transport)
