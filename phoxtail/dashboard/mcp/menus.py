"""MCP tools for reading and writing the menus shown on the dashboard."""

from __future__ import annotations

import json

from phoxtail.dashboard.mcp._error import error_envelope
from phoxtail.dashboard.mcp._http import get_json, request
from phoxtail.mcp import mcp_server
from phoxtail.mcp.authorization import scoped

ENTRY_SHAPES = (
    "Entries are stream data: a list of {'type': ..., 'value': {...}} objects. "
    "Five types exist. "
    "'page' — {'page': <page id>, 'label': <optional override>, 'open_in_new_tab': <bool>}. "
    "'internal_link' — {'link': <InternalLink snippet id>, 'label': <optional override>, "
    "'open_in_new_tab': <bool>}; list the snippets with "
    "phoxtail_content_list_internal_links. "
    "'external_link' — {'url': <absolute URL>, 'label': <optional>, 'open_in_new_tab': <bool>}. "
    "'dropdown' — {'label': <required>, 'items': [<entries of the four other types>]}; "
    "dropdowns do not nest inside each other. "
    "'separator' — {'label': <optional heading for what follows>}."
)


@mcp_server.tool(
    name="phoxtail_dashboard_list_menus",
    auth=[scoped("phoxtail_dashboard.view_menu")],
    description=(
        "List the menus shown along the top of the dashboard. A menu belongs to one "
        "site in one language. Optionally filter by `site` or `locale` ID. Returns a "
        "summary of each menu including how many entries it holds — call "
        "phoxtail_dashboard_get_menu for the entries themselves."
    ),
)
def list_menus(site: int | None = None, locale: int | None = None) -> str:
    return json.dumps(get_json("/menus/", site=site, locale=locale), indent=2)


@mcp_server.tool(
    name="phoxtail_dashboard_get_menu",
    auth=[scoped("phoxtail_dashboard.view_menu")],
    description=(
        "Get one dashboard menu with all of its entries as JSON. Also returns the "
        "current ETag, which MUST be passed to phoxtail_dashboard_update_menu for "
        "concurrency control. Pass the `uuid` from "
        "phoxtail_dashboard_list_menus."
    ),
)
def get_menu(menu_uuid: str) -> str:
    resp = request("GET", f"/menus/{menu_uuid}/")
    envelope = error_envelope(resp)
    if envelope:
        return envelope
    data = resp.json()
    data["_etag"] = resp.headers.get("ETag", "")
    return json.dumps(data, indent=2)


@mcp_server.tool(
    name="phoxtail_dashboard_create_menu",
    auth=[scoped("phoxtail_dashboard.add_menu")],
    description=(
        "Write the dashboard menu for one site in one language. A site and language "
        "can hold a single menu, so this fails with a conflict if one already exists "
        "— update that one instead. " + ENTRY_SHAPES
    ),
)
def create_menu(site_id: int, locale_id: int, items: list[dict] | None = None) -> str:
    resp = request(
        "POST",
        "/menus/",
        json_body={"site_id": site_id, "locale_id": locale_id, "items": items or []},
    )
    envelope = error_envelope(resp)
    if envelope:
        return envelope
    data = resp.json()
    data["_etag"] = resp.headers.get("ETag", "")
    return json.dumps(data, indent=2)


@mcp_server.tool(
    name="phoxtail_dashboard_update_menu",
    auth=[scoped("phoxtail_dashboard.change_menu")],
    description=(
        "Replace a dashboard menu's entries. Requires the ETag from a prior "
        "phoxtail_dashboard_get_menu call. `items` is the complete new list — entries "
        "left out are removed, so fetch the menu first and send the whole set. A menu's "
        "site and language cannot change; they are what identify it. " + ENTRY_SHAPES
    ),
)
def update_menu(menu_uuid: str, etag: str, items: list[dict]) -> str:
    resp = request(
        "PATCH",
        f"/menus/{menu_uuid}/",
        json_body={"items": items},
        headers={"If-Match": etag},
    )
    envelope = error_envelope(resp)
    if envelope:
        return envelope
    data = resp.json()
    data["_etag"] = resp.headers.get("ETag", "")
    return json.dumps(data, indent=2)


@mcp_server.tool(
    name="phoxtail_dashboard_delete_menu",
    auth=[scoped("phoxtail_dashboard.delete_menu")],
    description=(
        "Delete a dashboard menu. The dashboard stays readable in that language — it simply shows no menu bar."
    ),
)
def delete_menu(menu_uuid: str) -> str:
    resp = request("DELETE", f"/menus/{menu_uuid}/")
    envelope = error_envelope(resp)
    if envelope:
        return envelope
    return json.dumps({"deleted": menu_uuid})
