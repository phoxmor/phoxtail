"""Shared HTTP client for the Phoxtail MCP server.

Every MCP tool issues HTTP requests against the running Phoxtail API.
This module centralises the base-URL resolution, request dispatch, and
JSON convenience helpers so that domain tool modules stay focused on
business logic.

Unlike the CLI client (``phoxtail.cli.studio.client``), errors are
raised as exceptions rather than calling ``typer.Exit``. The MCP tool
wrappers catch these and return structured error JSON to the agent.
"""

from __future__ import annotations

from typing import Any

import httpx

from phoxtail.cli.utils.config import get_api_base_url
from phoxtail.cli.utils.credentials import resolve_token

API_PREFIX = "/api/streams/v1"
DEFAULT_TIMEOUT = 30.0


def api_base_url() -> str:
    """Resolve the API base URL for the current project.

    Thin wrapper around ``phoxtail.cli.utils.config.get_api_base_url`` —
    kept as a module-level name so tool modules can keep importing
    ``from phoxtail.mcp._http import api_base_url``.
    """
    return get_api_base_url()


def url(path: str) -> str:
    """Build a full URL for the given API path."""
    return f"{api_base_url()}{API_PREFIX}{path}"


def request(
    method: str,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    json_body: Any | None = None,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    """Issue an HTTP request against the streams v1 API.

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
    return httpx.request(
        method,
        url(path),
        params=clean_params or None,
        json=json_body,
        headers=final_headers or None,
        timeout=DEFAULT_TIMEOUT,
        follow_redirects=True,
    )


def get_json(path: str, **params: Any) -> dict[str, Any]:
    """GET convenience — returns parsed JSON or raises on failure."""
    resp = request("GET", path, params=params)
    resp.raise_for_status()
    return resp.json()
