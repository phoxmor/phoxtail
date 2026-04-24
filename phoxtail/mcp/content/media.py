"""``phoxtail_pages_list_*`` MCP tools for image + document lookup."""

from __future__ import annotations

import json

from mcp.server.fastmcp import Image as MCPImage

from phoxtail.mcp import mcp_server
from phoxtail.mcp.content._http import request
from phoxtail.mcp.content.pages import _write_error_envelope


def _lookup(path: str, search: str | None, limit: int) -> str:
    resp = request("GET", path, params={"search": search, "limit": limit})
    envelope = _write_error_envelope(resp)
    if envelope is not None:
        return envelope
    return json.dumps(resp.json(), indent=2)


@mcp_server.tool(
    name="phoxtail_pages_list_images",
    description=(
        "Search images in the Wagtail media library by title. "
        "Returns a list of {id, title, width, height, description, tags, focal_point, file_url}. "
        "To view an image visually, call `phoxtail_images_view(image_id)` — "
        "do not curl `file_url`. "
        "The integer `id` is the value to pass wherever a block or page "
        "field expects an Image FK."
    ),
)
def list_images(search: str | None = None, limit: int = 50) -> str:
    return _lookup("/media/images/", search, limit)


@mcp_server.tool(
    name="phoxtail_images_upload",
    description=(
        "Upload a new image to the Wagtail media library from a local file path. "
        "Returns {id, title, description, file_url} of the created image."
    ),
)
def upload_image(file_path: str, title: str) -> str:
    import mimetypes
    from pathlib import Path

    import httpx

    from phoxtail.cli.utils.credentials import resolve_token
    from phoxtail.mcp._http import api_base_url, url

    path = Path(file_path)
    if not path.exists():
        return json.dumps({"error": f"File not found: {file_path}"})

    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    headers = {}
    token = resolve_token(api_base_url())
    if token:
        headers["Authorization"] = f"Bearer {token}"

    with path.open("rb") as f:
        resp = httpx.post(
            url("/api/content/v1/media/images/"),
            files={"file": (path.name, f, mime)},
            data={"title": title},
            headers=headers,
            timeout=60.0,
            follow_redirects=True,
        )
    envelope = _write_error_envelope(resp)
    if envelope is not None:
        return envelope
    return json.dumps(resp.json(), indent=2)


@mcp_server.tool(
    name="phoxtail_images_get",
    description=(
        "Fetch a single Wagtail image by its numeric ID. "
        "Returns {id, title, width, height, description, tags, focal_point, file_url}. "
        "`width` and `height` are the actual stored pixel dimensions — use these "
        "when calculating focal_point coordinates; do not guess from the rendered view. "
        "To view the image visually, call `phoxtail_images_view(image_id)` — "
        "do not curl `file_url`."
    ),
)
def get_image(image_id: int) -> str:
    resp = request("GET", f"/media/images/{image_id}/")
    envelope = _write_error_envelope(resp)
    if envelope is not None:
        return envelope
    return json.dumps(resp.json(), indent=2)


@mcp_server.tool(
    name="phoxtail_images_view",
    description=(
        "Fetch a Wagtail image by numeric ID and return its visual content directly. "
        "Use this whenever you need to see what an image looks like — "
        "do NOT attempt to download image URLs via shell/curl; "
        "this tool is the correct way to view images."
    ),
)
def view_image(image_id: int):
    resp = request("GET", f"/media/images/{image_id}/view/")
    if resp.status_code != 200:
        return json.dumps({"error": f"Image {image_id} not found or unavailable"})
    return MCPImage(data=resp.content, format="jpeg")


@mcp_server.tool(
    name="phoxtail_images_update",
    description=(
        "Update a Wagtail image's metadata by numeric ID. All fields are optional; "
        "omitted fields are left untouched. "
        "`title` renames the image. "
        "`description` is the alt-text/caption. "
        "`tags` is a full replacement list (pass [] to clear all tags). "
        "`focal_point` is {x, y, width, height} in pixels relative to the full stored "
        "image — always call `phoxtail_images_get` first to obtain the real `width` "
        "and `height`, then scale your coordinates accordingly. "
        "Do NOT estimate dimensions from the rendered view returned by `phoxtail_images_view`."
    ),
)
def update_image(
    image_id: int,
    title: str | None = None,
    description: str | None = None,
    tags: list[str] | None = None,
    focal_point: dict | None = None,
) -> str:
    payload: dict = {}
    if title is not None:
        payload["title"] = title
    if description is not None:
        payload["description"] = description
    if tags is not None:
        payload["tags"] = tags
    if focal_point is not None:
        payload["focal_point"] = focal_point
    resp = request("PATCH", f"/media/images/{image_id}/", json_body=payload)
    envelope = _write_error_envelope(resp)
    if envelope is not None:
        return envelope
    return json.dumps(resp.json(), indent=2)


@mcp_server.tool(
    name="phoxtail_pages_list_documents",
    description=(
        "Search documents in the Wagtail library by title. Returns a list "
        "of {id, title, file_url}. The integer `id` is the value to pass "
        "wherever a block or page field expects a Document FK."
    ),
)
def list_documents(search: str | None = None, limit: int = 50) -> str:
    return _lookup("/media/documents/", search, limit)
