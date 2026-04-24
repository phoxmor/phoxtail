"""MCP tools for listing, reading, creating, updating, and deleting internal links."""

from __future__ import annotations

import json
from typing import Any

from phoxtail.mcp import mcp_server
from phoxtail.mcp.content._http import get_json, request


@mcp_server.tool(
    name="phoxtail_content_list_internal_links",
    description=(
        "List all internal links. An internal link maps a display label to a "
        "named Django URL (e.g. 'dashboard:index') for use in StreamField blocks "
        "such as navbars and footers. Optionally pass `search` for a prefix search "
        "on label and url_name."
    ),
)
def list_internal_links(search: str | None = None) -> str:
    return json.dumps(get_json("/internal-links/", search=search), indent=2)


@mcp_server.tool(
    name="phoxtail_content_get_internal_link",
    description=(
        "Get the full detail of a single internal link, including its resolved URL. "
        "Also returns the current ETag which MUST be passed to "
        "phoxtail_content_update_internal_link for concurrency control. "
        "Pass the integer `link_id` from phoxtail_content_list_internal_links."
    ),
)
def get_internal_link(link_id: int) -> str:
    resp = request("GET", f"/internal-links/{link_id}/")
    resp.raise_for_status()
    data = resp.json()
    data["_etag"] = resp.headers.get("ETag", "")
    return json.dumps(data, indent=2)


@mcp_server.tool(
    name="phoxtail_content_create_internal_link",
    description=(
        "Create a new internal link. Requires a human-readable `label` and a "
        "Django `url_name` (e.g. 'dashboard:index'). The url_name must resolve "
        "in the project's URL configuration — the server will return a 400 if it "
        "does not. Returns the created link with its ETag."
    ),
)
def create_internal_link(label: str, url_name: str) -> str:
    resp = request("POST", "/internal-links/", json_body={"label": label, "url_name": url_name})

    if resp.status_code == 409:
        return json.dumps(
            {
                "error": "conflict",
                "detail": resp.json().get("detail", "InternalLink already exists."),
            }
        )
    if resp.status_code == 400:
        return json.dumps(
            {
                "error": "validation_error",
                "detail": resp.json().get("detail", "Invalid data."),
            }
        )
    resp.raise_for_status()

    data = resp.json()
    data["_etag"] = resp.headers.get("ETag", "")
    return json.dumps(data, indent=2)


@mcp_server.tool(
    name="phoxtail_content_update_internal_link",
    description=(
        "Update an internal link's label and/or url_name. Requires the ETag from a "
        "prior phoxtail_content_get_internal_link call for optimistic concurrency "
        "control. Omitted fields are left untouched. The url_name must resolve in "
        "the project's URL configuration. On success, returns the updated link with "
        "a new ETag."
    ),
)
def update_internal_link(
    link_id: int,
    etag: str,
    label: str | None = None,
    url_name: str | None = None,
) -> str:
    body: dict[str, Any] = {}
    if label is not None:
        body["label"] = label
    if url_name is not None:
        body["url_name"] = url_name

    resp = request(
        "PATCH",
        f"/internal-links/{link_id}/",
        json_body=body,
        headers={"If-Match": etag},
    )

    if resp.status_code == 412:
        return json.dumps(
            {
                "error": "conflict",
                "detail": (
                    "The link has been modified since you last read it. "
                    "Call phoxtail_content_get_internal_link again to get the "
                    "current content and ETag, then retry."
                ),
            }
        )
    if resp.status_code == 428:
        return json.dumps(
            {
                "error": "precondition_required",
                "detail": (
                    "ETag is required. Call phoxtail_content_get_internal_link "
                    "first and pass the _etag value from the response."
                ),
            }
        )
    if resp.status_code == 400:
        return json.dumps(
            {
                "error": "validation_error",
                "detail": resp.json().get("detail", "Invalid data."),
            }
        )
    resp.raise_for_status()

    data = resp.json()
    data["_etag"] = resp.headers.get("ETag", "")
    return json.dumps(data, indent=2)


@mcp_server.tool(
    name="phoxtail_content_delete_internal_link",
    description=(
        "Delete an internal link by numeric ID. Pass the integer `link_id` from "
        "phoxtail_content_list_internal_links."
    ),
)
def delete_internal_link(link_id: int) -> str:
    resp = request("DELETE", f"/internal-links/{link_id}/")

    if resp.status_code == 404:
        return json.dumps(
            {
                "error": "not_found",
                "detail": resp.json().get("detail", f"InternalLink {link_id} not found."),
            }
        )
    resp.raise_for_status()
    return json.dumps({"deleted": link_id})
