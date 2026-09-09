"""Tests for pass-through caller identity in phoxtail.mcp._http.

When the MCP server runs over HTTP, the caller's Bearer token — not the
server's own stored token — must reach the project API, so every action is
attributed to whoever actually asked. The MCP layer never validates the
token; the API is the sole authority.
"""

import asyncio
import json
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import patch

from phoxtail.mcp._http import caller_bearer, outbound_token, request, serving_over_http


@contextmanager
def _serving(headers: dict[str, str]):
    """Present an inbound HTTP request the way the transport would.

    The single place in this file that knows *how* a served HTTP request
    is made visible to the tool layer. Everything below asserts behaviour
    through the public gate functions, so a change of SDK moves this
    helper and nothing else.

    Stubs the lookup rather than standing up a server: what the gate
    functions do with an inbound request is the subject here. That the
    lookup itself answers correctly per transport — populated over HTTP,
    absent over stdio — is a property of fastmcp, verified against both
    real transports before this migration.
    """
    with patch("phoxtail.mcp._http._inbound_http_request", return_value=SimpleNamespace(headers=headers)):
        yield


class TestCallerBearer:
    def test_none_outside_any_mcp_request(self):
        """stdio and the in-process chatbot never have an HTTP request."""
        assert caller_bearer() is None

    def test_reads_the_bearer_of_the_request_being_served(self):
        with _serving({"authorization": "Bearer phxt_abc"}):
            assert caller_bearer() == "phxt_abc"

    def test_ignores_non_bearer_schemes(self):
        with _serving({"authorization": "Basic dXNlcjpwdw=="}):
            assert caller_bearer() is None

    def test_none_when_no_authorization_header(self):
        with _serving({}):
            assert caller_bearer() is None


class TestRequestIdentity:
    def test_caller_token_wins_over_the_stored_one(self):
        """Pass-through identity: the API must see the caller, not this
        process's own credentials."""
        with _serving({"authorization": "Bearer phxt_caller"}):
            with (
                patch("phoxtail.mcp._http.resolve_token", return_value="phxt_stored") as stored,
                patch("phoxtail.mcp._http.httpx.request") as mock_request,
            ):
                request("GET", "/api/streams/v1/blocks/")

        sent = mock_request.call_args.kwargs["headers"]
        assert sent["Authorization"] == "Bearer phxt_caller"
        stored.assert_not_called()

    def test_stored_token_used_when_no_caller(self):
        """No request context at all (stdio): the ambient, operator-owned
        token is correct — the process already runs as that operator."""
        with (
            patch("phoxtail.mcp._http.resolve_token", return_value="phxt_stored"),
            patch("phoxtail.mcp._http.httpx.request") as mock_request,
        ):
            request("GET", "/api/streams/v1/blocks/")

        sent = mock_request.call_args.kwargs["headers"]
        assert sent["Authorization"] == "Bearer phxt_stored"

    def test_stored_token_not_used_when_http_caller_sends_no_bearer(self):
        """An HTTP request context with no Authorization header must not
        fall back to this machine's own stored token — that would let
        anyone reachable on the network borrow the operator's identity."""
        with _serving({}):
            with (
                patch("phoxtail.mcp._http.resolve_token", return_value="phxt_stored") as stored,
                patch("phoxtail.mcp._http.httpx.request") as mock_request,
            ):
                request("GET", "/api/streams/v1/blocks/")

        sent = mock_request.call_args.kwargs["headers"] or {}
        assert "Authorization" not in sent
        stored.assert_not_called()


class TestOutboundToken:
    """The gate as tools actually call it.

    Most tool modules reach ``outbound_token`` directly rather than
    through ``request`` — ``peers``, ``studio.render``, ``content.media``
    and ``design.font_weights`` all build their own httpx calls. Testing
    only the ``request`` path would leave that majority unguarded.
    """

    def test_forwards_the_caller_over_http(self):
        with _serving({"authorization": "Bearer phxt_caller"}):
            with patch("phoxtail.mcp._http.resolve_token", return_value="phxt_stored") as stored:
                assert outbound_token() == "phxt_caller"
            stored.assert_not_called()

    def test_yields_nothing_when_an_http_caller_sends_no_bearer(self):
        """The borrowed-identity guard, at the gate itself: a caller who
        brought no credential gets none, and the API refuses them."""
        with _serving({}):
            with patch("phoxtail.mcp._http.resolve_token", return_value="phxt_stored") as stored:
                assert outbound_token() is None
            stored.assert_not_called()

    def test_uses_the_ambient_token_over_stdio(self):
        with patch("phoxtail.mcp._http.resolve_token", return_value="phxt_stored"):
            assert outbound_token() == "phxt_stored"


class TestOutboundTokenForAPeer:
    """The peer hop (``phoxtail_peer_call``), which passes the peer's own
    address so the stored token looked up is the one for *that* project.

    Over stdio the address must select the peer's credential — sending
    this project's token to a sibling gets a 401, since a token issued by
    one project is not valid for another. Over HTTP the address must be
    ignored entirely: an unauthenticated network caller must not be able
    to borrow the operator's identity against a *third* project merely
    because this machine holds a token for it.
    """

    def test_selects_the_peers_stored_token_over_stdio(self):
        with patch("phoxtail.mcp._http.resolve_token", return_value="phxt_peer") as stored:
            assert outbound_token("http://beta-site.localhost") == "phxt_peer"
        stored.assert_called_once_with("http://beta-site.localhost")

    def test_ignores_the_peer_address_over_http(self):
        with _serving({"authorization": "Bearer phxt_caller"}):
            with patch("phoxtail.mcp._http.resolve_token", return_value="phxt_peer") as stored:
                assert outbound_token("http://beta-site.localhost") == "phxt_caller"
            stored.assert_not_called()

    def test_yields_nothing_for_an_unauthenticated_http_caller(self):
        with _serving({}):
            with patch("phoxtail.mcp._http.resolve_token", return_value="phxt_peer") as stored:
                assert outbound_token("http://beta-site.localhost") is None
            stored.assert_not_called()


class TestAgainstRealTransports:
    """The gate driven end-to-end, over transports rather than stubs.

    Everything above stubs the request lookup, which is right for asking
    what the gate *does* with an inbound request — but it cannot catch the
    failure that matters most: an SDK whose lookup stops distinguishing
    the transports. Then ``serving_over_http()`` answers False under HTTP,
    ``outbound_token()`` falls back to this machine's stored token, and
    every anonymous caller on the network acts as the operator. Nothing
    raises; no stubbed test fails.

    So these run phoxtail's own gate functions inside a real MCP server,
    reached once over streamable-http and once not. The HTTP side goes
    through an in-process ASGI transport: real headers and a real request
    object, but no port to bind and no thread to race.
    """

    @staticmethod
    def _probe_server():
        from fastmcp import FastMCP

        server = FastMCP("identity-probe")

        @server.tool
        def probe() -> str:
            import json

            return json.dumps(
                {
                    "over_http": serving_over_http(),
                    "bearer": caller_bearer(),
                    "outbound": outbound_token(),
                }
            )

        return server

    @staticmethod
    def _call(server, transport):
        import json

        from fastmcp import Client

        async def run():
            async with Client(transport) as client:
                result = await client.call_tool("probe")
            return json.loads(result.content[0].text)

        return asyncio.run(run())

    def test_a_streamable_http_caller_is_seen_as_one(self):
        import httpx2
        from fastmcp import Client
        from fastmcp.client.transports import StreamableHttpTransport

        server = self._probe_server()
        app = server.http_app(path="/mcp")

        def factory(**kwargs):
            kwargs.pop("transport", None)
            return httpx2.AsyncClient(
                transport=httpx2.ASGITransport(app=app),
                base_url="http://identity-probe",
                **kwargs,
            )

        async def run(headers):
            transport = StreamableHttpTransport(
                "http://identity-probe/mcp", headers=headers, httpx_client_factory=factory
            )
            async with app.router.lifespan_context(app):
                async with Client(transport) as client:
                    result = await client.call_tool("probe")
            return json.loads(result.content[0].text)

        with patch("phoxtail.mcp._http.resolve_token", return_value="phxt_stored"):
            seen = asyncio.run(run({"Authorization": "Bearer phxt_caller"}))
            assert seen == {"over_http": True, "bearer": "phxt_caller", "outbound": "phxt_caller"}

            # The borrowed-identity case, end to end: a caller who brought
            # no credential must not be handed the operator's.
            anonymous = asyncio.run(run(None))
            assert anonymous == {"over_http": True, "bearer": None, "outbound": None}

    def test_a_non_http_caller_is_not(self):
        from fastmcp.client.transports import FastMCPTransport

        server = self._probe_server()
        with patch("phoxtail.mcp._http.resolve_token", return_value="phxt_stored"):
            seen = self._call(server, FastMCPTransport(server))
        assert seen == {"over_http": False, "bearer": None, "outbound": "phxt_stored"}

    def test_concurrent_callers_do_not_see_each_others_identity(self):
        """Two overlapping HTTP calls, two different Bearers.

        The gate reads an ambient per-request context rather than taking
        the token as an argument, so "which request am I serving" is
        answered by machinery this project does not own. If that context
        were shared instead of per-task, one caller would act as another —
        the worst failure this module can have, and a silent one.
        """
        import httpx2
        from fastmcp import Client, FastMCP
        from fastmcp.client.transports import StreamableHttpTransport

        server = FastMCP("identity-probe")

        @server.tool
        async def slow_probe(delay: float) -> str:
            # Overlap the two calls inside the server: each must still
            # read its own request while the other is in flight.
            await asyncio.sleep(delay)
            return json.dumps({"bearer": caller_bearer(), "outbound": outbound_token()})

        app = server.http_app(path="/mcp")

        def factory(**kwargs):
            kwargs.pop("transport", None)
            return httpx2.AsyncClient(
                transport=httpx2.ASGITransport(app=app), base_url="http://identity-probe", **kwargs
            )

        async def call(token, delay):
            transport = StreamableHttpTransport(
                "http://identity-probe/mcp",
                headers={"Authorization": f"Bearer {token}"},
                httpx_client_factory=factory,
            )
            async with Client(transport) as client:
                result = await client.call_tool("slow_probe", {"delay": delay})
            return json.loads(result.content[0].text)

        async def both():
            async with app.router.lifespan_context(app):
                return await asyncio.gather(call("phxt_alice", 0.10), call("phxt_bob", 0.01))

        with patch("phoxtail.mcp._http.resolve_token", return_value="phxt_stored"):
            alice, bob = asyncio.run(both())

        assert alice == {"bearer": "phxt_alice", "outbound": "phxt_alice"}
        assert bob == {"bearer": "phxt_bob", "outbound": "phxt_bob"}
