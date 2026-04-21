"""``phoxtail_pages_*`` MCP tools for listing, reading, and writing pages."""

from __future__ import annotations

import json
from typing import Any

from phoxtail.mcp import mcp_server
from phoxtail.mcp.pages._http import request, get_json



# ---------------------------------------------------------------------------
# List / get
# ---------------------------------------------------------------------------


@mcp_server.tool(
    name="phoxtail_pages_list_pages",
    description=(
        "List Wagtail pages in the project. Optional filters: `type` "
        "(e.g. 'phoxtail_blog.BlogPostPage'), `parent` (parent page id), "
        "`live` (published status). Returns a slim summary — call "
        "phoxtail_pages_get_page for a full detail including the body."
    ),
)
def list_pages(
    type: str | None = None,
    parent: int | None = None,
    live: bool | None = None,
    limit: int = 50,
    offset: int = 0,
) -> str:
    resp = request(
        "GET",
        "/pages/",
        params={
            "type": type,
            "parent": parent,
            "live": live,
            "limit": limit,
            "offset": offset,
        },
    )
    envelope = _write_error_envelope(resp)
    if envelope is not None:
        return envelope
    return json.dumps(resp.json(), indent=2)


@mcp_server.tool(
    name="phoxtail_pages_get_page",
    description=(
        "Get the full detail of a single page: common Wagtail fields, "
        "per-page-type fields contributed by the owning app, and the "
        "body as a list of {type, value, id} blocks. The response "
        "includes `_etag` which MUST be passed back on any subsequent "
        "write call (phoxtail_pages_update_page, phoxtail_pages_publish, "
        "phoxtail_pages_replace_body) for optimistic concurrency control."
    ),
)
def get_page(page_id: int) -> str:
    resp = request("GET", f"/pages/{page_id}/")
    envelope = _write_error_envelope(resp)
    if envelope is not None:
        return envelope
    data = resp.json()
    data["_etag"] = resp.headers.get("ETag", "")
    return json.dumps(data, indent=2)


# ---------------------------------------------------------------------------
# Patch / publish / unpublish
# ---------------------------------------------------------------------------


_ERROR_LABELS = {
    400: "validation_error",
    403: "permission_denied",
    404: "not_found",
    409: "conflict",
    412: "precondition_failed",
    428: "precondition_required",
}


def _safe_detail(resp, fallback: str) -> str:
    try:
        payload = resp.json()
    except (ValueError, TypeError):
        return fallback
    if isinstance(payload, dict):
        return str(payload.get("detail") or fallback)
    return fallback


def _write_error_envelope(resp) -> str | None:
    """Translate any non-2xx response into a structured JSON envelope.

    Returns the JSON string to surface to the agent, or ``None`` if the
    response is a success (2xx) and the caller should proceed normally.

    The spec (``pages-domain.md`` → "Error taxonomy") promises that MCP
    tools never leak raw HTTP exceptions to the agent — every failure
    becomes a reason-able ``{"error", "detail", "status"}`` payload.
    """
    sc = resp.status_code
    if 200 <= sc < 300:
        return None

    specific_hints = {
        412: (
            "The page has been modified since you last read it. Call "
            "phoxtail_pages_get_page again and retry with the fresh _etag."
        ),
        428: (
            "etag is required. Call phoxtail_pages_get_page and pass "
            "the _etag from its response."
        ),
        409: (
            "The server refused the write because of a conflicting "
            "state (e.g. no draft revision yet). Re-read the page and "
            "retry."
        ),
    }
    fallback = specific_hints.get(sc, f"Request failed with HTTP {sc}.")
    return json.dumps(
        {
            "error": _ERROR_LABELS.get(sc, "http_error"),
            "status": sc,
            "detail": _safe_detail(resp, fallback),
        }
    )


@mcp_server.tool(
    name="phoxtail_pages_update_page",
    description=(
        "Patch a page's scalar fields (title, slug, seo_title, "
        "search_description, plus any per-type fields contributed by the "
        "owning app — e.g. intro/author/read_mins on BlogPostPage). "
        "Creates a draft revision; does NOT publish. Pass `etag` from a "
        "prior phoxtail_pages_get_page. On success, returns the updated "
        "page with a fresh `_etag` you can keep using for further writes."
    ),
)
def update_page(
    page_id: int,
    etag: str,
    fields: dict[str, Any],
) -> str:
    resp = request(
        "PATCH",
        f"/pages/{page_id}/",
        json_body=fields,
        headers={"If-Match": etag},
    )
    envelope = _write_error_envelope(resp)
    if envelope is not None:
        return envelope
    resp.raise_for_status()
    data = resp.json()
    data["_etag"] = resp.headers.get("ETag", "")
    return json.dumps(data, indent=2)


@mcp_server.tool(
    name="phoxtail_pages_publish",
    description=(
        "Publish the latest draft revision of a page. Requires the "
        "ETag from a prior phoxtail_pages_get_page call. On success, "
        "the page becomes live and the URL becomes non-null."
    ),
)
def publish_page(page_id: int, etag: str) -> str:
    resp = request(
        "POST",
        f"/pages/{page_id}/publish/",
        headers={"If-Match": etag},
    )
    envelope = _write_error_envelope(resp)
    if envelope is not None:
        return envelope
    resp.raise_for_status()
    data = resp.json()
    data["_etag"] = resp.headers.get("ETag", "")
    return json.dumps(data, indent=2)


@mcp_server.tool(
    name="phoxtail_pages_unpublish",
    description=(
        "Take a page offline. Requires the ETag from a prior "
        "phoxtail_pages_get_page call."
    ),
)
def unpublish_page(page_id: int, etag: str) -> str:
    resp = request(
        "POST",
        f"/pages/{page_id}/unpublish/",
        headers={"If-Match": etag},
    )
    envelope = _write_error_envelope(resp)
    if envelope is not None:
        return envelope
    resp.raise_for_status()
    data = resp.json()
    data["_etag"] = resp.headers.get("ETag", "")
    return json.dumps(data, indent=2)
