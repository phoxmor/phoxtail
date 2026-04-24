"""HTTP client for the Phoxtail content v1 API."""

from __future__ import annotations

import json
from typing import Any

import httpx
import typer
from rich.console import Console

from phoxtail.cli.utils.config import get_api_base_url
from phoxtail.cli.utils.credentials import resolve_token

EXIT_GENERAL_FAILURE = 1
EXIT_ENVIRONMENT = 2

API_PREFIX = "/api/content/v1"
DEFAULT_TIMEOUT = 30.0

console = Console()


def _api_base_url() -> str:
    return get_api_base_url()


def _url(path: str) -> str:
    return f"{_api_base_url()}{API_PREFIX}{path}"


def request(
    method: str,
    path: str,
    *,
    params: dict[str, Any] | None = None,
) -> httpx.Response:
    clean_params = {k: v for k, v in (params or {}).items() if v is not None}
    token = resolve_token(_api_base_url())
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    try:
        response = httpx.request(
            method,
            _url(path),
            params=clean_params or None,
            headers=headers or None,
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

    if response.status_code >= 400:
        _raise_for_error(response)

    return response


def _raise_for_error(response: httpx.Response) -> None:
    try:
        payload = response.json()
        detail = (
            (
                payload.get("detail")
                or payload.get("message")
                or f"HTTP {response.status_code}: {payload}"
            )
            if isinstance(payload, dict)
            else f"HTTP {response.status_code}: {payload}"
        )
    except ValueError:
        detail = response.text or f"HTTP {response.status_code}"
    console.print(f"[red]Error:[/red] {detail}")
    if response.status_code == 401:
        console.print(
            "Run [bold]phoxtail auth login[/bold] to store an API token, "
            "or set [bold]$PHOXTAIL_API_TOKEN[/bold]."
        )
    raise typer.Exit(code=EXIT_GENERAL_FAILURE)


def list_pages(
    *,
    type: str | None = None,
    parent: int | None = None,
    live: bool | None = None,
    search: str | None = None,
    locale: str | None = None,
    site: int | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    return request(
        "GET",
        "/pages/",
        params={
            "type": type,
            "parent": parent,
            "live": live,
            "search": search,
            "locale": locale,
            "site": site,
            "limit": limit,
            "offset": offset,
        },
    ).json()


def list_images(*, search: str | None = None, limit: int = 50) -> dict[str, Any]:
    return request(
        "GET", "/media/images/", params={"search": search, "limit": limit}
    ).json()


def list_documents(*, search: str | None = None, limit: int = 50) -> dict[str, Any]:
    return request(
        "GET", "/media/documents/", params={"search": search, "limit": limit}
    ).json()


def list_videos(*, search: str | None = None, limit: int = 50) -> dict[str, Any]:
    return request(
        "GET", "/media/videos/", params={"search": search, "limit": limit}
    ).json()


def list_audio(*, search: str | None = None, limit: int = 50) -> dict[str, Any]:
    return request(
        "GET", "/media/audio/", params={"search": search, "limit": limit}
    ).json()


def list_locales() -> dict[str, Any]:
    return request("GET", "/locales/").json()


def list_sites() -> dict[str, Any]:
    return request("GET", "/sites/").json()


def emit_json(data: Any) -> None:
    print(json.dumps(data, indent=2, default=str))
