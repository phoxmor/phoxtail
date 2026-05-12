"""``phoxtail_sites_*`` MCP tools for listing and managing Wagtail sites."""

from __future__ import annotations

import json

from phoxtail.mcp import mcp_server
from phoxtail.mcp.content._http import request
from phoxtail.mcp.content.pages import _write_error_envelope


@mcp_server.tool(
    name="phoxtail_sites_list",
    description=(
        "List all Wagtail Site instances configured in this project. "
        "Returns each site's id, hostname, port, site_name, root_page_id, "
        "is_default_site, and root_url. Use the id when filtering pages by "
        "site (phoxtail_pages_list_pages site= argument), and root_page_id "
        "to navigate the page tree rooted at that site."
    ),
)
def sites_list() -> str:
    resp = request("GET", "/sites/")
    envelope = _write_error_envelope(resp)
    if envelope is not None:
        return envelope
    return json.dumps(resp.json(), indent=2)


@mcp_server.tool(
    name="phoxtail_sites_get",
    description=(
        "Get the full detail of a single Wagtail site by id. "
        "The response includes `_etag` which MUST be passed back on any "
        "subsequent write call (phoxtail_sites_update, phoxtail_sites_delete) "
        "for optimistic concurrency control."
    ),
)
def sites_get(site_id: int) -> str:
    resp = request("GET", f"/sites/{site_id}/")
    envelope = _write_error_envelope(resp)
    if envelope is not None:
        return envelope
    data = resp.json()
    data["_etag"] = resp.headers.get("ETag", "")
    return json.dumps(data, indent=2)


@mcp_server.tool(
    name="phoxtail_sites_create",
    description=(
        "Create a new Wagtail Site instance. "
        "Before calling: use phoxtail_pages_list_pages to find an existing "
        "page to use as root_page_id — every site must be rooted at a page. "
        "hostname is lowercased automatically. port defaults to 80. "
        "site_name is optional (human-readable label). "
        "Set is_default_site=true to make this the fallback site for "
        "unmatched hostnames — only one site can be the default at a time; "
        "if another site is already default the call returns a conflict error "
        "and you must unset the existing default first via phoxtail_sites_update. "
        "Returns the created site including its root_url and an `_etag`."
    ),
)
def sites_create(
    hostname: str,
    root_page_id: int,
    port: int = 80,
    site_name: str = "",
    is_default_site: bool = False,
) -> str:
    resp = request(
        "POST",
        "/sites/",
        json_body={
            "hostname": hostname,
            "port": port,
            "site_name": site_name,
            "root_page_id": root_page_id,
            "is_default_site": is_default_site,
        },
    )
    envelope = _write_error_envelope(resp)
    if envelope is not None:
        return envelope
    data = resp.json()
    data["_etag"] = resp.headers.get("ETag", "")
    return json.dumps(data, indent=2)


@mcp_server.tool(
    name="phoxtail_sites_update",
    description=(
        "Update a Wagtail site's fields. Pass only the fields you want to "
        "change — omitted fields are left untouched. "
        "Requires `etag` from a prior phoxtail_sites_get call. "
        "Writable fields: hostname, port, site_name, root_page_id, is_default_site. "
        "Setting is_default_site=true fails with a conflict error if another "
        "site is already the default — unset that site first. "
        "Returns the updated site with a fresh `_etag`."
    ),
)
def sites_update(
    site_id: int,
    etag: str,
    hostname: str | None = None,
    port: int | None = None,
    site_name: str | None = None,
    root_page_id: int | None = None,
    is_default_site: bool | None = None,
) -> str:
    fields: dict = {}
    if hostname is not None:
        fields["hostname"] = hostname
    if port is not None:
        fields["port"] = port
    if site_name is not None:
        fields["site_name"] = site_name
    if root_page_id is not None:
        fields["root_page_id"] = root_page_id
    if is_default_site is not None:
        fields["is_default_site"] = is_default_site

    resp = request(
        "PATCH",
        f"/sites/{site_id}/",
        json_body=fields,
        headers={"If-Match": etag},
    )
    envelope = _write_error_envelope(resp)
    if envelope is not None:
        return envelope
    data = resp.json()
    data["_etag"] = resp.headers.get("ETag", "")
    return json.dumps(data, indent=2)


@mcp_server.tool(
    name="phoxtail_sites_delete",
    description=(
        "Permanently delete a Wagtail site. Requires `etag` from a prior "
        "phoxtail_sites_get call. "
        "WARNING: deleting the default site leaves no fallback for hostnames "
        "that do not match any remaining site — requests to unknown hostnames "
        "will stop resolving. Verify another site has is_default_site=true "
        "before deleting the current default. "
        "Deleting a site does NOT delete its root page or any page tree."
    ),
)
def sites_delete(site_id: int, etag: str) -> str:
    resp = request(
        "DELETE",
        f"/sites/{site_id}/",
        headers={"If-Match": etag},
    )
    envelope = _write_error_envelope(resp)
    if envelope is not None:
        return envelope
    return json.dumps({"deleted": site_id})
