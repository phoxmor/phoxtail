"""HTTP client for the Phoxtail streams v1 and content v1 APIs.

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
import mimetypes
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
import typer
from rich.console import Console

from phoxtail.cli.utils.config import get_api_base_url
from phoxtail.cli.utils.credentials import resolve_token

# Exit codes are documented in docs/studio/cli.md:
EXIT_GENERAL_FAILURE = 1
EXIT_ENVIRONMENT = 2

API_PREFIX = "/api/streams/v1"
CONTENT_API_PREFIX = "/api/content/v1"

# Module-level override set by commands that accept a --peer flag.
# When set, this takes precedence over phoxtail.toml and the default.
_peer_url_override: str | None = None


def set_peer(url: str | None) -> None:
    """Override the API base URL for the lifetime of the current command.

    Call this early in any command that accepts ``--peer``.  Pass ``None``
    to clear (used in tests).
    """
    global _peer_url_override
    _peer_url_override = url.rstrip("/") if url else None


# Generous enough for prompt-render (LLM-size templates) but short enough
# that a stopped container surfaces as an error quickly.
DEFAULT_TIMEOUT = 30.0

console = Console()


def _api_base_url() -> str:
    """Resolve the API base URL for the current project.

    Priority order:
    1. ``set_peer()`` override (set by commands that accept ``--peer``)
    2. Shared ``get_api_base_url()`` — reads ``[studio] api_url`` or falls
       back to ``http://localhost``.
    """
    if _peer_url_override is not None:
        return _peer_url_override
    return get_api_base_url()


def _url(path: str) -> str:
    return f"{_api_base_url()}{API_PREFIX}{path}"


def _content_url(path: str) -> str:
    return f"{_api_base_url()}{CONTENT_API_PREFIX}{path}"


def _auth_headers() -> dict[str, str]:
    """Return an Authorization header dict for the current project token."""
    token = resolve_token(_api_base_url())
    return {"Authorization": f"Bearer {token}"} if token else {}


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
    final_headers = dict(headers or {})
    if "Authorization" not in final_headers:
        token = resolve_token(_api_base_url())
        if token:
            final_headers["Authorization"] = f"Bearer {token}"
    try:
        response = httpx.request(
            method,
            _url(path),
            params=clean_params or None,
            json=json_body,
            headers=final_headers or None,
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
    if response.status_code == 401:
        console.print("Run [bold]phoxtail auth login[/bold] to store an API token.")
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
        return payload.get("detail") or payload.get("message") or f"HTTP {response.status_code}: {payload}"
    return f"HTTP {response.status_code}: {payload}"


# ---------------------------------------------------------------------------
# Typed helpers (one per endpoint the CLI uses)
# ---------------------------------------------------------------------------


def get_json(path: str, **params: Any) -> dict[str, Any]:
    return request("GET", path, params=params).json()


def list_page_type_app_labels() -> set[str]:
    data = get_json("/page-types/")
    return set(data.get("app_labels", []))


def list_variants(
    block: str | None = None,
    collection: str | None = None,
    search: str | None = None,
) -> dict[str, Any]:
    return get_json("/variants/", block=block, collection=collection, search=search)


def list_collections(search: str | None = None) -> dict[str, Any]:
    return get_json("/collections/", search=search)


def list_blocks(search: str | None = None) -> dict[str, Any]:
    return get_json("/blocks/", search=search)


def get_variant_by_id(variant_id: int) -> tuple[dict[str, Any], str | None]:
    """Fetch a variant by its numeric ID and return ``(body, etag)``."""
    response = request("GET", f"/variants/{variant_id}/")
    return response.json(), response.headers.get("ETag")


def update_variant_by_id(
    variant_id: int,
    *,
    name: str | None = None,
    description: str | None = None,
    html: str | None = None,
    css: str | None = None,
    javascript: str | None = None,
    is_default: bool | None = None,
    etag: str,
) -> tuple[dict[str, Any], int, str | None]:
    body: dict[str, Any] = {}
    if name is not None:
        body["name"] = name
    if description is not None:
        body["description"] = description
    if html is not None:
        body["html"] = html
    if css is not None:
        body["css"] = css
    if javascript is not None:
        body["javascript"] = javascript
    if is_default is not None:
        body["is_default"] = is_default
    response = request(
        "PUT",
        f"/variants/{variant_id}/",
        json_body=body,
        headers={"If-Match": etag},
        allow_status=(400,),
    )
    return response.json(), response.status_code, response.headers.get("ETag")


def update_collection_by_id(
    collection_id: int,
    *,
    name: str,
    description: str,
    template: str,
    etag: str,
) -> tuple[dict[str, Any], int, str | None]:
    response = request(
        "PATCH",
        f"/collections/{collection_id}/",
        json_body={"name": name, "description": description, "template": template},
        headers={"If-Match": etag},
        allow_status=(400,),
    )
    return response.json(), response.status_code, response.headers.get("ETag")


def update_block_by_id(
    block_id: int,
    *,
    name: str,
    description: str,
    icon: str,
    group: str,
    is_shared: bool,
    page_types: list[str],
    schema: list[dict],
    sort_order: int,
    etag: str,
) -> tuple[dict[str, Any], int, str | None]:
    response = request(
        "PATCH",
        f"/blocks/{block_id}/",
        json_body={
            "name": name,
            "description": description,
            "icon": icon,
            "group": group,
            "is_shared": is_shared,
            "page_types": page_types,
            "schema": schema,
            "sort_order": sort_order,
        },
        headers={"If-Match": etag},
        allow_status=(400,),
    )
    return response.json(), response.status_code, response.headers.get("ETag")


def create_variant(
    *,
    identifier: str,
    name: str,
    block_id: int,
    collection_id: int,
    description: str = "",
    html: str = "",
    css: str = "",
    javascript: str = "",
    is_default: bool = False,
) -> tuple[dict[str, Any], int, str | None]:
    """Create a new variant. Returns ``(body, status_code, etag)``.

    201 = created, 409 = already exists (skip).
    """
    response = request(
        "POST",
        "/variants/",
        json_body={
            "identifier": identifier,
            "name": name,
            "block_id": block_id,
            "collection_id": collection_id,
            "description": description,
            "html": html,
            "css": css,
            "javascript": javascript,
            "is_default": is_default,
        },
        allow_status=(409, 400),
    )
    return response.json(), response.status_code, response.headers.get("ETag")


def get_collection_by_id(collection_id: int) -> tuple[dict[str, Any], str | None]:
    response = request("GET", f"/collections/{collection_id}/")
    return response.json(), response.headers.get("ETag")


def create_collection(
    *,
    identifier: str,
    name: str,
    description: str = "",
    template: str = "",
) -> tuple[dict[str, Any], int]:
    """Create a new collection. Returns ``(body, status_code)``.

    The caller is responsible for checking status_code: 201 = created,
    409 = already exists (skip).
    """
    response = request(
        "POST",
        "/collections/",
        json_body={
            "identifier": identifier,
            "name": name,
            "description": description,
            "template": template,
        },
        allow_status=(409, 400),
    )
    return response.json(), response.status_code


def create_block(
    *,
    identifier: str,
    name: str,
    description: str = "",
    icon: str = "",
    group: str = "",
    is_shared: bool = False,
    page_types: list[str] | None = None,
    schema: list[dict] | None = None,
    sort_order: int = 0,
) -> tuple[dict[str, Any], int]:
    """Create a new block. Returns ``(body, status_code)``.

    201 = created, 409 = already exists (skip).
    """
    response = request(
        "POST",
        "/blocks/",
        json_body={
            "identifier": identifier,
            "name": name,
            "description": description,
            "icon": icon,
            "group": group,
            "is_shared": is_shared,
            "page_types": page_types or [],
            "schema": schema or [],
            "sort_order": sort_order,
        },
        allow_status=(409, 400),
    )
    return response.json(), response.status_code


def get_block_by_id(block_id: int) -> tuple[dict[str, Any], str | None]:
    response = request("GET", f"/blocks/{block_id}/")
    return response.json(), response.headers.get("ETag")


def get_context(
    *,
    block_id: int,
    collection_id: int | None = None,
    references: list[int] | None = None,
) -> dict[str, Any]:
    """Fetch assembled context data for an AI agent briefing."""
    body: dict[str, Any] = {"block_id": block_id}
    if collection_id is not None:
        body["collection_id"] = collection_id
    if references:
        body["references"] = references
    response = request("POST", "/context/", json_body=body)
    return response.json()


def emit_json(data: Any) -> None:
    """Print a value to stdout as pretty-printed JSON (no Rich markup)."""
    print(json.dumps(data, indent=2, default=str))


# ---------------------------------------------------------------------------
# Image helpers (content v1 API)
# ---------------------------------------------------------------------------


def download_bytes(url: str) -> bytes | None:
    """Download a URL and return raw bytes, or None on any failure.

    Auth header is only sent when the target host matches the API base URL
    (i.e. local dev server).  External hosts like S3 or a CDN receive no token.
    """
    api_host = urlparse(_api_base_url()).netloc
    url_host = urlparse(url).netloc
    headers = _auth_headers() if url_host == api_host else {}
    try:
        response = httpx.get(url, headers=headers, timeout=DEFAULT_TIMEOUT, follow_redirects=True)
        if response.status_code == 200:
            return response.content
    except httpx.HTTPError:
        pass
    return None


def upload_image(*, title: str, file_path: Path) -> tuple[dict[str, Any], int]:
    """Upload an image to the Wagtail image library. Returns ``(body, status_code)``.

    201 = uploaded successfully (body has ``id``). Other 4xx = validation/auth
    error (caller should warn+skip). Connection failures still raise ``typer.Exit``
    because they indicate the server is unreachable.
    """
    mime_type = mimetypes.guess_type(str(file_path))[0] or "image/png"
    try:
        with open(file_path, "rb") as f:
            response = httpx.post(
                _content_url("/images/"),
                data={"title": title},
                files={"file": (file_path.name, f, mime_type)},
                headers=_auth_headers(),
                timeout=DEFAULT_TIMEOUT,
                follow_redirects=True,
            )
    except httpx.ConnectError as exc:
        console.print(
            "[red]Error:[/red] could not reach the Phoxtail API at "
            f"[bold]{_api_base_url()}{CONTENT_API_PREFIX}[/bold]. "
            "Is the dev server running ([bold]docker compose up[/bold])?"
        )
        raise typer.Exit(code=EXIT_ENVIRONMENT) from exc
    except httpx.HTTPError as exc:
        console.print(f"[red]Error:[/red] HTTP request failed: {exc}")
        raise typer.Exit(code=EXIT_ENVIRONMENT) from exc
    return response.json(), response.status_code


def search_images(title: str) -> list[dict[str, Any]]:
    """Search the image library by title substring. Returns list of image dicts."""
    try:
        response = httpx.get(
            _content_url("/images/"),
            params={"search": title, "limit": 50},
            headers=_auth_headers(),
            timeout=DEFAULT_TIMEOUT,
            follow_redirects=True,
        )
        if response.status_code == 200:
            return response.json().get("items", [])
    except httpx.HTTPError:
        pass
    return []


def attach_variant_previews(
    variant_id: int,
    *,
    image_ids: dict[str, int | None],
    etag: str,
) -> tuple[dict[str, Any], int, str | None]:
    """Attach preview images to a variant via a partial PUT.

    ``image_ids`` maps VariantUpdate field names (e.g. ``preview_image_desktop_id``)
    to image PKs. Only the supplied keys are sent so other fields are untouched.
    """
    response = request(
        "PUT",
        f"/variants/{variant_id}/",
        json_body=image_ids,
        headers={"If-Match": etag},
        allow_status=(400,),
    )
    return response.json(), response.status_code, response.headers.get("ETag")
