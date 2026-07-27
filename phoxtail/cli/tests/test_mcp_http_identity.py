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

from phoxtail.mcp._http import caller_bearer, request


def _serving(headers: dict[str, str]):
    """Enter the SDK's per-request context as the HTTP transport would."""
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
