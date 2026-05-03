"""Shared HTTP client for the Phoxtail MCP server.

Every MCP tool issues HTTP requests against the running Phoxtail API.
This module centralises the base-URL resolution, request dispatch, and
JSON convenience helpers so that domain tool modules stay focused on
business logic.

Unlike earlier drafts, this module does **not** inject an ``/api/<domain>``
prefix. Domain tool modules pass full paths starting with ``/api/`` so
that tools from any domain (``/api/streams/v1/...``, ``/api/content/v1/...``,
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


def url(path: str) -> str:
    """Build a full URL for the given API path.

    ``path`` must start with ``/api/`` — domain tool modules are
    responsible for including their own prefix (e.g. ``/api/content/v1/``).
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
        token = resolve_token(api_base_url())
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
