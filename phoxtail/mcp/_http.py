"""Shared HTTP client for the Phoxtail MCP server.

Every MCP tool issues HTTP requests against the running Phoxtail API.
This module centralises the base-URL resolution, request dispatch, and
JSON convenience helpers so that domain tool modules stay focused on
business logic.

Unlike earlier drafts, this module does **not** inject an ``/api/<domain>``
prefix. Domain tool modules pass full paths starting with ``/api/`` so
that tools from any domain (``/api/streams/v1/...``, ``/api/cms/v1/...``,
``/api/blog/v1/...``, ...) share one client.

Unlike the CLI client (``phoxtail.cli.studio.client``), errors are
raised as exceptions rather than calling ``typer.Exit``. The MCP tool
wrappers catch these and return structured error JSON to the agent.
"""

from __future__ import annotations

from typing import Any

import httpx

from phoxtail.cli.utils.config import get_api_base_url
from phoxtail.cli.utils.credentials import resolve_token

DEFAULT_TIMEOUT = 30.0


def api_base_url() -> str:
    """Resolve the API base URL for the current project."""
    return get_api_base_url()


def _inbound_http_request():
    """The underlying HTTP request for the MCP call being served, if any.

    ``get_http_request()`` raises rather than returning ``None`` when no
    HTTP request is in flight, and that is exactly the signal wanted: it
    is populated only by the streamable-http transport, so a raise means
    stdio, an in-process call, or a direct call in a test. Verified
    against both real transports, since a wrong answer here is silent —
    see the tests in ``test_mcp_http_identity``.

    Not ``get_http_headers()``: that helper strips ``authorization`` from
    what it returns, which would quietly reduce every HTTP caller to
    having sent no credential.
    """
    from fastmcp.server.dependencies import get_http_request

    try:
        return get_http_request()
    except RuntimeError:
        return None


def serving_over_http() -> bool:
    """Whether this MCP call arrived over the streamable-http transport.

    Callers use this to decide whether ambient, operator-owned
    credentials (``resolve_token``) are safe to fall back on. Over stdio
    they are (the process already runs as whoever launched it); over
    HTTP they are not (anyone reachable on the network is "whoever
    launched it" otherwise), so the caller's own Bearer, or nothing, is
    all that fallback should ever produce there.
    """
    return _inbound_http_request() is not None


def caller_bearer() -> str | None:
    """The Bearer token of the MCP request currently being served, if any.

    Returns ``None`` both when there is no ``Authorization`` header and
    when this call isn't over HTTP at all (stdio) — callers that need to
    tell those apart should check :func:`serving_over_http` first. The
    MCP layer never validates this token — tools forward it to the API,
    which is the sole authority, so a caller acts on this project exactly
    as far as this project's Django lets that token act. Reads the
    per-request context established around each tool invocation; that
    concurrent callers cannot see each other's identity is asserted by
    test, not assumed.
    """
    http_request = _inbound_http_request()
    if http_request is None:
        return None
    auth = http_request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip() or None
    return None


def outbound_token(ambient_url: str | None = None) -> str | None:
    """The token to send with an outbound API call — the one gate every
    tool must go through, not just ``request()``.

    Over HTTP the caller's own Bearer is the only source: falling back to
    this process's stored token would let anyone reachable on the network
    act as whoever is logged in on this machine. Over stdio there is no
    caller to forward, and the process already runs as the operator, so
    the ambient token for *ambient_url* (defaulting to this project's own
    API) is exactly right.
    """
    if serving_over_http():
        return caller_bearer()
    return resolve_token(ambient_url or api_base_url())


def url(path: str) -> str:
    """Build a full URL for the given API path.

    ``path`` must start with ``/api/`` — domain tool modules are
    responsible for including their own prefix (e.g. ``/api/cms/v1/``).
    """
    if not path.startswith("/"):
        path = "/" + path
    return f"{api_base_url()}{path}"


def request(
    method: str,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    json_body: Any | None = None,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    """Issue an HTTP request against the Phoxtail API.

    Returns the raw ``httpx.Response``. Errors are **not** caught here —
    callers decide how to surface failures (structured JSON for MCP
    tools, Rich output for CLI commands).
    """
    clean_params = {k: v for k, v in (params or {}).items() if v is not None}
    final_headers = dict(headers or {})
    if "Authorization" not in final_headers:
        token = outbound_token()
        if token:
            final_headers["Authorization"] = f"Bearer {token}"
    resp = httpx.request(
        method,
        url(path),
        params=clean_params or None,
        json=json_body,
        headers=final_headers or None,
        timeout=DEFAULT_TIMEOUT,
        follow_redirects=True,
    )
    return resp


def get_json(path: str, **params: Any) -> dict[str, Any]:
    """GET convenience — returns parsed JSON or raises on failure."""
    resp = request("GET", path, params=params)
    resp.raise_for_status()
    return resp.json()


def bind_prefix(api_prefix: str):
    """Return ``(request, get_json)`` partial-applied with a path prefix.

    Domain tool modules call this once at import time so their code can
    write paths like ``/variants/`` without repeating
    ``/api/<domain>/v1`` on every call::

        request, get_json = bind_prefix("/api/streams/v1")
        get_json("/variants/")  # → GET /api/streams/v1/variants/

    Prefer this over re-importing the bare ``request`` + concatenating
    manually — one call site, one constant per module.
    """

    def _request(
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: Any | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        return request(
            method,
            api_prefix + path,
            params=params,
            json_body=json_body,
            headers=headers,
        )

    def _get_json(path: str, **params: Any) -> dict[str, Any]:
        return get_json(api_prefix + path, **params)

    return _request, _get_json
