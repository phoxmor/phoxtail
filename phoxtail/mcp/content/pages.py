"""``phoxtail_pages_*`` MCP tools for listing, reading, and writing pages."""

from __future__ import annotations

import json
from typing import Any

from phoxtail.mcp import mcp_server
from phoxtail.mcp.content._http import request

# ---------------------------------------------------------------------------
# List / get
# ---------------------------------------------------------------------------


@mcp_server.tool(
    name="phoxtail_pages_list_pages",
    description=(
        "List Wagtail pages in the project. Optional filters: `type` "
        "(e.g. 'phoxtail_blog.BlogPostPage'), `parent` (parent page id), "
        "`live` (published status), `search` (prefix search on title — "
        "use this to find a parent page by name), `locale` (language code "
        "e.g. 'en'), `site` (site id). Returns a slim summary — call "
        "phoxtail_pages_get_page for a full detail including the body."
    ),
)
def list_pages(
    type: str | None = None,
    parent: int | None = None,
    live: bool | None = None,
    search: str | None = None,
    locale: str | None = None,
    site: int | None = None,
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
            "search": search,
            "locale": locale,
            "site": site,
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
    # Split common Wagtail scalars from contributed (per-type) fields so
    # the API can dispatch them to the right handler. See PagePatch.
    common_keys = {"title", "slug", "seo_title", "search_description"}
    body: dict[str, Any] = {k: v for k, v in fields.items() if k in common_keys}
    contributed = {k: v for k, v in fields.items() if k not in common_keys}
    if contributed:
        body["fields"] = contributed
    resp = request(
        "PATCH",
        f"/pages/{page_id}/",
        json_body=body,
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
    name="phoxtail_pages_create_page",
    description=(
        "Create a new Wagtail page as a draft under a given parent. "
        "Before calling this tool: (1) call phoxtail_page_types_list to "
        "discover the correct `type` string and which fields are required; "
        "(2) call phoxtail_pages_list_pages with `search` to find the "
        "parent page ID; (3) resolve any FK fields (e.g. author, image) "
        "via the lookup tool listed in fk_lookups. "
        "The page is created as a draft — call phoxtail_pages_publish to "
        "make it live. Returns the created page with an `_etag` for "
        "subsequent write calls."
    ),
)
def create_page(
    type: str,
    parent: int,
    title: str,
    slug: str | None = None,
    fields: dict[str, Any] | None = None,
) -> str:
    body: dict[str, Any] = {"type": type, "parent": parent, "title": title}
    if slug is not None:
        body["slug"] = slug
    if fields:
        # Split common Wagtail scalars from contributed (per-type) fields
        # so the API can dispatch them correctly. See PageCreate.
        common_keys = {"seo_title", "search_description"}
        contributed = {}
        for k, v in fields.items():
            if k in common_keys:
                body[k] = v
            else:
                contributed[k] = v
        if contributed:
            body["fields"] = contributed
    resp = request("POST", "/pages/", json_body=body)
    envelope = _write_error_envelope(resp)
    if envelope is not None:
        return envelope
    data = resp.json()
    data["_etag"] = resp.headers.get("ETag", "")
    return json.dumps(data, indent=2)


@mcp_server.tool(
    name="phoxtail_pages_delete_page",
    description=(
        "Permanently delete a page. Requires the ETag from a prior "
        "phoxtail_pages_get_page call. Pass force=true to also delete all "
        "child pages; without it the call is rejected if the page has "
        "children. This action is irreversible."
    ),
)
def delete_page(page_id: int, etag: str, force: bool = False) -> str:
    resp = request(
        "DELETE",
        f"/pages/{page_id}/",
        params={"force": "true"} if force else {},
        headers={"If-Match": etag},
    )
    envelope = _write_error_envelope(resp)
    if envelope is not None:
        return envelope
    return json.dumps({"deleted": page_id})


@mcp_server.tool(
    name="phoxtail_pages_translate_page",
    description=(
        "Copy a Wagtail page into a new locale using simple_translation. "
        "Before calling: use phoxtail_locales_list to discover available "
        "locale IDs. The copied page is created as a draft in the target "
        "locale under the translated parent — call phoxtail_pages_publish "
        "on the returned page ID to make it live. "
        "include_subtree=true also copies all child pages recursively (like "
        "the Wagtail admin 'Include subtree' checkbox). "
        "copy_parents=true automatically copies any untranslated ancestor "
        "pages as aliases. alias=true creates a live-synced alias instead "
        "of an independent editable copy. "
        "Returns the new top-level page with an _etag for further writes."
    ),
)
def translate_page(
    page_id: int,
    locale_id: int,
    copy_parents: bool = False,
    alias: bool = False,
    include_subtree: bool = False,
) -> str:
    resp = request(
        "POST",
        f"/pages/{page_id}/copy_for_translation/",
        json_body={
            "locale": locale_id,
            "copy_parents": copy_parents,
            "alias": alias,
            "include_subtree": include_subtree,
        },
    )
    envelope = _write_error_envelope(resp)
    if envelope is not None:
        return envelope
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
