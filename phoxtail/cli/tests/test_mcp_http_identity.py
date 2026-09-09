"""Tests for pass-through caller identity in phoxtail.mcp._http.

When the MCP server runs over HTTP, the caller's Bearer token — not the
server's own stored token — must reach the project API, so every action is
attributed to whoever actually asked. The MCP layer never validates the
token; the API is the sole authority.
"""

from types import SimpleNamespace
from unittest.mock import patch

from mcp.server.lowlevel.server import request_ctx
from mcp.shared.context import RequestContext

from phoxtail.mcp._http import caller_bearer, outbound_token, request, serving_over_http


def _serving(headers: dict[str, str]):
    """Enter the SDK's per-request context as the HTTP transport would.

    The single place in this file that knows *how* an inbound HTTP request
    is made visible to the tool layer. Everything below asserts behaviour
    through the public gate functions, so a change of SDK moves this
    helper and nothing else.
    """
    return request_ctx.set(
        RequestContext(
            request_id=1,
            meta=None,
            session=None,
            lifespan_context=None,
            request=SimpleNamespace(headers=headers),
        )
    )


class TestCallerBearer:
    def test_none_outside_any_mcp_request(self):
        """stdio and the in-process chatbot never have an HTTP request."""
        assert caller_bearer() is None

    def test_reads_the_bearer_of_the_request_being_served(self):
        token = _serving({"authorization": "Bearer phxt_abc"})
        try:
            assert caller_bearer() == "phxt_abc"
        finally:
            request_ctx.reset(token)

    def test_ignores_non_bearer_schemes(self):
        token = _serving({"authorization": "Basic dXNlcjpwdw=="})
        try:
            assert caller_bearer() is None
        finally:
            request_ctx.reset(token)

    def test_none_when_no_authorization_header(self):
        token = _serving({})
        try:
            assert caller_bearer() is None
        finally:
            request_ctx.reset(token)


class TestRequestIdentity:
    def test_caller_token_wins_over_the_stored_one(self):
        """Pass-through identity: the API must see the caller, not this
        process's own credentials."""
        token = _serving({"authorization": "Bearer phxt_caller"})
        try:
            with (
                patch("phoxtail.mcp._http.resolve_token", return_value="phxt_stored") as stored,
                patch("phoxtail.mcp._http.httpx.request") as mock_request,
            ):
                request("GET", "/api/streams/v1/blocks/")
        finally:
            request_ctx.reset(token)

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
        token = _serving({})
        try:
            with (
                patch("phoxtail.mcp._http.resolve_token", return_value="phxt_stored") as stored,
                patch("phoxtail.mcp._http.httpx.request") as mock_request,
            ):
                request("GET", "/api/streams/v1/blocks/")
        finally:
            request_ctx.reset(token)

        sent = mock_request.call_args.kwargs["headers"] or {}
        assert "Authorization" not in sent
        stored.assert_not_called()


class TestServingOverHttp:
    """The branch every other guarantee here rests on.

    ``outbound_token`` trusts this function to say whether an ambient,
    operator-owned credential is safe to fall back on. A wrong ``False``
    is silent — no exception, no failing call — and hands the operator's
    identity to anyone who can reach the port. Assert it directly rather
    than only through its consequences.
    """

    def test_false_without_an_inbound_http_request(self):
        assert serving_over_http() is False

    def test_true_while_serving_one(self):
        token = _serving({})
        try:
            assert serving_over_http() is True
        finally:
            request_ctx.reset(token)


class TestOutboundToken:
    """The gate as tools actually call it.

    Most tool modules reach ``outbound_token`` directly rather than
    through ``request`` — ``peers``, ``studio.render``, ``content.media``
    and ``design.font_weights`` all build their own httpx calls. Testing
    only the ``request`` path would leave that majority unguarded.
    """

    def test_forwards_the_caller_over_http(self):
        token = _serving({"authorization": "Bearer phxt_caller"})
        try:
            with patch("phoxtail.mcp._http.resolve_token", return_value="phxt_stored") as stored:
                assert outbound_token() == "phxt_caller"
            stored.assert_not_called()
        finally:
            request_ctx.reset(token)

    def test_yields_nothing_when_an_http_caller_sends_no_bearer(self):
        """The borrowed-identity guard, at the gate itself: a caller who
        brought no credential gets none, and the API refuses them."""
        token = _serving({})
        try:
            with patch("phoxtail.mcp._http.resolve_token", return_value="phxt_stored") as stored:
                assert outbound_token() is None
            stored.assert_not_called()
        finally:
            request_ctx.reset(token)

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
        token = _serving({"authorization": "Bearer phxt_caller"})
        try:
            with patch("phoxtail.mcp._http.resolve_token", return_value="phxt_peer") as stored:
                assert outbound_token("http://beta-site.localhost") == "phxt_caller"
            stored.assert_not_called()
        finally:
            request_ctx.reset(token)

    def test_yields_nothing_for_an_unauthenticated_http_caller(self):
        token = _serving({})
        try:
            with patch("phoxtail.mcp._http.resolve_token", return_value="phxt_peer") as stored:
                assert outbound_token("http://beta-site.localhost") is None
            stored.assert_not_called()
        finally:
            request_ctx.reset(token)
