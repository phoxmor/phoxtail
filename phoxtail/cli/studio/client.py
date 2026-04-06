"""HTTP client for the Phoxtail streams v1 API.

Every Studio CLI verb calls the API through this module. The client:

- Reads the API base URL from the project's ``phoxtail.toml`` (with a
  localhost default) so a designer doesn't have to pass it on every call.
- Surfaces Ninja's structured error responses as clean Rich-formatted
  messages and the documented exit codes (1/2/3 — see cli.md).
- Provides thin wrappers for the endpoints the CLI actually uses, so
  verb modules never construct URLs or parse JSON by hand.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import typer
from rich.console import Console

from phoxtail.cli.utils.config import _find_config_file, load_config

# Exit codes are documented in docs/studio/cli.md:
EXIT_GENERAL_FAILURE = 1
EXIT_ENVIRONMENT = 2

# Default base URL when a project has not configured one explicitly.
# Matches the port docker-compose exposes for the dev app.
DEFAULT_BASE_URL = "http://localhost:8000"
API_PREFIX = "/api/streams/v1"

# Generous enough for prompt-render (LLM-size templates) but short enough
# that a stopped container surfaces as an error quickly.
DEFAULT_TIMEOUT = 30.0

console = Console()


def _api_base_url() -> str:
    """Resolve the API base URL for the current project.

    Looks for ``[studio] api_url`` in ``phoxtail.toml``; falls back to
    ``DEFAULT_BASE_URL``. Trailing slashes are normalized so callers can
    safely concatenate path segments.
    """
    if _find_config_file() is None:
        return DEFAULT_BASE_URL
    try:
        config = load_config()
    except Exception:
        return DEFAULT_BASE_URL
    studio = config.get("studio") or {}
    url = studio.get("api_url") or DEFAULT_BASE_URL
    return url.rstrip("/")


def _url(path: str) -> str:
    return f"{_api_base_url()}{API_PREFIX}{path}"


# ---------------------------------------------------------------------------
# Low-level request
# ---------------------------------------------------------------------------


def request(
    method: str,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    json_body: Any | None = None,
    headers: dict[str, str] | None = None,
    allow_status: tuple[int, ...] = (),
) -> httpx.Response:
    """Issue an HTTP request to the streams v1 API.

    Returns the raw ``httpx.Response`` so callers can inspect headers
    (ETag) when needed. Any connection failure is mapped to the
    documented environment exit code; 4xx/5xx statuses are mapped to the
    general-failure exit code with the server's detail message *unless*
    the status is in ``allow_status``, in which case the response is
    returned as-is for the caller to handle (used by the edit verb's
    template-cascade logic).
    """
    # Filter out None params so httpx does not send empty query values.
    clean_params = {k: v for k, v in (params or {}).items() if v is not None}
    try:
        response = httpx.request(
            method,
            _url(path),
            params=clean_params or None,
            json=json_body,
            headers=headers,
            timeout=DEFAULT_TIMEOUT,
            follow_redirects=True,
        )
    except httpx.ConnectError as exc:
        console.print(
            "[red]Error:[/red] could not reach the Phoxtail API at "
            f"[bold]{_api_base_url()}{API_PREFIX}[/bold]. "
            "Is the dev server running ([bold]docker compose up[/bold])?"
        )
        raise typer.Exit(code=EXIT_ENVIRONMENT) from exc
    except httpx.HTTPError as exc:
        console.print(f"[red]Error:[/red] HTTP request failed: {exc}")
        raise typer.Exit(code=EXIT_ENVIRONMENT) from exc

    if response.status_code >= 400 and response.status_code not in allow_status:
        _raise_for_error(response)

    return response


def _raise_for_error(response: httpx.Response) -> None:
    detail = _extract_detail(response)
    console.print(f"[red]Error:[/red] {detail}")
    raise typer.Exit(code=EXIT_GENERAL_FAILURE)


def _extract_detail(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        # Guard against HTML error pages (e.g. from wagtail's catch-all).
        content_type = response.headers.get("content-type", "")
        if "html" in content_type:
            return f"HTTP {response.status_code} (server returned an HTML error page)"
        return response.text or f"HTTP {response.status_code}"
    if isinstance(payload, dict):
        return (
            payload.get("detail")
            or payload.get("message")
            or f"HTTP {response.status_code}: {payload}"
        )
    return f"HTTP {response.status_code}: {payload}"


# ---------------------------------------------------------------------------
# Typed helpers (one per endpoint the CLI uses)
# ---------------------------------------------------------------------------


def get_json(path: str, **params: Any) -> dict[str, Any]:
    return request("GET", path, params=params).json()


def list_variants(
    block: str | None = None, collection: str | None = None
) -> dict[str, Any]:
    return get_json("/variants/", block=block, collection=collection)


def list_collections() -> dict[str, Any]:
    return get_json("/collections/")


def list_blocks() -> dict[str, Any]:
    return get_json("/blocks/")


def list_prompts() -> dict[str, Any]:
    return get_json("/prompts/")


def get_variant(
    identifier: str,
    block: str,
    collection: str | None = None,
) -> tuple[dict[str, Any], str | None]:
    """Fetch a variant and return ``(body, etag)``.

    The ETag is forwarded from the response header so callers that
    intend to commit can send it back as ``If-Match``.
    """
    response = request(
        "GET",
        f"/variants/{identifier}/",
        params={"block": block, "collection": collection},
    )
    return response.json(), response.headers.get("ETag")


def update_variant(
    identifier: str,
    *,
    html: str,
    css: str,
    javascript: str,
    etag: str,
    block: str,
    collection: str | None = None,
) -> dict[str, Any]:
    response = request(
        "PUT",
        f"/variants/{identifier}/",
        params={"block": block, "collection": collection},
        json_body={"html": html, "css": css, "javascript": javascript},
        headers={"If-Match": etag},
    )
    return response.json()


def create_variant(
    *,
    identifier: str,
    name: str,
    block: str,
    collection: str,
    description: str = "",
    html: str = "",
    css: str = "",
    javascript: str = "",
) -> tuple[dict[str, Any], str | None]:
    """Create a new variant and return ``(body, etag)``."""
    response = request(
        "POST",
        "/variants/",
        json_body={
            "identifier": identifier,
            "name": name,
            "block": block,
            "collection": collection,
            "description": description,
            "html": html,
            "css": css,
            "javascript": javascript,
        },
    )
    return response.json(), response.headers.get("ETag")


def get_collection(identifier: str) -> dict[str, Any]:
    return get_json(f"/collections/{identifier}/")


def get_block(identifier: str) -> dict[str, Any]:
    return get_json(f"/blocks/{identifier}/")


def get_prompt(identifier: str) -> dict[str, Any]:
    return get_json(f"/prompts/{identifier}/")


def get_context(
    *,
    block: str,
    variant: str,
    references: list[str] | None = None,
) -> dict[str, Any]:
    """Fetch assembled context data for an AI agent briefing."""
    body: dict[str, Any] = {"block": block, "variant": variant}
    if references:
        body["references"] = references
    response = request("POST", "/context/", json_body=body)
    return response.json()


def render_prompt(
    template_identifier: str,
    *,
    variant: str,
    block: str,
    collection: str | None = None,
    references: list[str] | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {"variant": variant}
    if block:
        body["block"] = block
    if collection:
        body["collection"] = collection
    if references:
        body["references"] = references
    response = request(
        "POST",
        f"/prompts/{template_identifier}/render/",
        json_body=body,
    )
    return response.json()


def prompt_exists(identifier: str) -> bool:
    """Check whether a prompt identifier exists, without exiting on 404.

    Used by the edit verb to implement the ``variant_editor`` →
    ``variant_refiner`` template-cascade fallback.
    """
    response = request("GET", f"/prompts/{identifier}/", allow_status=(404,))
    return response.status_code == 200


def emit_json(data: Any) -> None:
    """Print a value to stdout as pretty-printed JSON (no Rich markup)."""
    print(json.dumps(data, indent=2, default=str))
