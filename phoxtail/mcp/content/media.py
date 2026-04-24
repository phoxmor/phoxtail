"""MCP tools for images, documents, videos, and audio."""

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


# ---------------------------------------------------------------------------
# Images
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------


@mcp_server.tool(
    name="phoxtail_pages_list_documents",
    description=(
        "Search documents in the Wagtail library by title. Returns a list of "
        "{id, title, tags, file_size, filename, file_extension, file_url}. "
        "The integer `id` is the value to pass wherever a block or page field "
        "expects a Document FK."
    ),
)
def list_documents(search: str | None = None, limit: int = 50) -> str:
    return _lookup("/media/documents/", search, limit)


@mcp_server.tool(
    name="phoxtail_documents_get",
    description=(
        "Fetch a single Wagtail document by its numeric ID. "
        "Returns {id, title, tags, file_size, filename, file_extension, file_url}."
    ),
)
def get_document(document_id: int) -> str:
    resp = request("GET", f"/media/documents/{document_id}/")
    envelope = _write_error_envelope(resp)
    if envelope is not None:
        return envelope
    return json.dumps(resp.json(), indent=2)


@mcp_server.tool(
    name="phoxtail_documents_upload",
    description=(
        "Upload a new document to the Wagtail library from a local file path. "
        "Returns {id, title, filename, file_extension, file_url} of the created document."
    ),
)
def upload_document(file_path: str, title: str) -> str:
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
            url("/api/content/v1/media/documents/"),
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
    name="phoxtail_documents_update",
    description=(
        "Update a Wagtail document's metadata by numeric ID. All fields are optional; "
        "omitted fields are left untouched. "
        "`title` renames the document. "
        "`tags` is a full replacement list (pass [] to clear all tags)."
    ),
)
def update_document(
    document_id: int,
    title: str | None = None,
    tags: list[str] | None = None,
) -> str:
    payload: dict = {}
    if title is not None:
        payload["title"] = title
    if tags is not None:
        payload["tags"] = tags
    resp = request("PATCH", f"/media/documents/{document_id}/", json_body=payload)
    envelope = _write_error_envelope(resp)
    if envelope is not None:
        return envelope
    return json.dumps(resp.json(), indent=2)


# ---------------------------------------------------------------------------
# Videos
# ---------------------------------------------------------------------------


@mcp_server.tool(
    name="phoxtail_videos_list",
    description=(
        "Search videos in the Wagtail media library by title. "
        "Returns a list of {id, title, duration, width, height, tags, file_url, thumbnail_url}. "
        "The integer `id` is the value to pass wherever a block or page field expects a Video FK."
    ),
)
def list_videos(search: str | None = None, limit: int = 50) -> str:
    return _lookup("/media/videos/", search, limit)


@mcp_server.tool(
    name="phoxtail_videos_get",
    description=(
        "Fetch a single Wagtail video by its numeric ID. "
        "Returns {id, title, duration, width, height, tags, file_url, thumbnail_url}."
    ),
)
def get_video(video_id: int) -> str:
    resp = request("GET", f"/media/videos/{video_id}/")
    envelope = _write_error_envelope(resp)
    if envelope is not None:
        return envelope
    return json.dumps(resp.json(), indent=2)


@mcp_server.tool(
    name="phoxtail_videos_upload",
    description=(
        "Upload a new video to the Wagtail media library from a local file path. "
        "`duration` is in seconds (float). `width` and `height` are pixel dimensions "
        "and are optional but recommended. "
        "Returns {id, title, duration, width, height, file_url} of the created video."
    ),
)
def upload_video(
    file_path: str,
    title: str,
    duration: float = 0.0,
    width: int | None = None,
    height: int | None = None,
) -> str:
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

    data: dict = {"title": title, "duration": str(duration)}
    if width is not None:
        data["width"] = str(width)
    if height is not None:
        data["height"] = str(height)

    with path.open("rb") as f:
        resp = httpx.post(
            url("/api/content/v1/media/videos/"),
            files={"file": (path.name, f, mime)},
            data=data,
            headers=headers,
            timeout=120.0,
            follow_redirects=True,
        )
    envelope = _write_error_envelope(resp)
    if envelope is not None:
        return envelope
    return json.dumps(resp.json(), indent=2)


@mcp_server.tool(
    name="phoxtail_videos_update",
    description=(
        "Update a Wagtail video's metadata by numeric ID. All fields are optional; "
        "omitted fields are left untouched. "
        "`duration` is in seconds. `width` and `height` are pixel dimensions. "
        "`tags` is a full replacement list (pass [] to clear all tags)."
    ),
)
def update_video(
    video_id: int,
    title: str | None = None,
    tags: list[str] | None = None,
    duration: float | None = None,
    width: int | None = None,
    height: int | None = None,
) -> str:
    payload: dict = {}
    if title is not None:
        payload["title"] = title
    if tags is not None:
        payload["tags"] = tags
    if duration is not None:
        payload["duration"] = duration
    if width is not None:
        payload["width"] = width
    if height is not None:
        payload["height"] = height
    resp = request("PATCH", f"/media/videos/{video_id}/", json_body=payload)
    envelope = _write_error_envelope(resp)
    if envelope is not None:
        return envelope
    return json.dumps(resp.json(), indent=2)


# ---------------------------------------------------------------------------
# Audio
# ---------------------------------------------------------------------------


@mcp_server.tool(
    name="phoxtail_audio_list",
    description=(
        "Search audio files in the Wagtail media library by title. "
        "Returns a list of {id, title, duration, tags, file_url}. "
        "The integer `id` is the value to pass wherever a block or page field expects an Audio FK."
    ),
)
def list_audio(search: str | None = None, limit: int = 50) -> str:
    return _lookup("/media/audio/", search, limit)


@mcp_server.tool(
    name="phoxtail_audio_get",
    description=(
        "Fetch a single Wagtail audio file by its numeric ID. "
        "Returns {id, title, duration, tags, file_url}."
    ),
)
def get_audio(audio_id: int) -> str:
    resp = request("GET", f"/media/audio/{audio_id}/")
    envelope = _write_error_envelope(resp)
    if envelope is not None:
        return envelope
    return json.dumps(resp.json(), indent=2)


@mcp_server.tool(
    name="phoxtail_audio_upload",
    description=(
        "Upload a new audio file to the Wagtail media library from a local file path. "
        "`duration` is in seconds (float). "
        "Returns {id, title, duration, file_url} of the created audio file."
    ),
)
def upload_audio(file_path: str, title: str, duration: float = 0.0) -> str:
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
            url("/api/content/v1/media/audio/"),
            files={"file": (path.name, f, mime)},
            data={"title": title, "duration": str(duration)},
            headers=headers,
            timeout=120.0,
            follow_redirects=True,
        )
    envelope = _write_error_envelope(resp)
    if envelope is not None:
        return envelope
    return json.dumps(resp.json(), indent=2)


@mcp_server.tool(
    name="phoxtail_audio_update",
    description=(
        "Update a Wagtail audio file's metadata by numeric ID. All fields are optional; "
        "omitted fields are left untouched. "
        "`duration` is in seconds. "
        "`tags` is a full replacement list (pass [] to clear all tags)."
    ),
)
def update_audio(
    audio_id: int,
    title: str | None = None,
    tags: list[str] | None = None,
    duration: float | None = None,
) -> str:
    payload: dict = {}
    if title is not None:
        payload["title"] = title
    if tags is not None:
        payload["tags"] = tags
    if duration is not None:
        payload["duration"] = duration
    resp = request("PATCH", f"/media/audio/{audio_id}/", json_body=payload)
    envelope = _write_error_envelope(resp)
    if envelope is not None:
        return envelope
    return json.dumps(resp.json(), indent=2)
