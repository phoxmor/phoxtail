"""MCP tools for images, documents, videos, and audio."""

from __future__ import annotations

import json

from mcp.server.fastmcp import Image as MCPImage

from phoxtail.mcp import mcp_server
from phoxtail.mcp.content._http import request
from phoxtail.mcp.content.pages import _write_error_envelope

# ---------------------------------------------------------------------------
# Images
# ---------------------------------------------------------------------------


@mcp_server.tool(
    name="phoxtail_pages_list_images",
    description=(
        "Search images in the media library by title. "
        "Returns a list of "
        "{id, title, width, height, description, tags, focal_point, file_url, collection_id}. "
        "Pass collection= to filter by a specific collection id "
        "(use phoxtail_collections_list to browse collections). "
        "To view an image visually, call `phoxtail_images_view(image_id)` — "
        "do not curl `file_url`. "
        "The integer `id` is the value to pass wherever a block or page "
        "field expects an Image FK."
    ),
)
def list_images(
    search: str | None = None, limit: int = 50, collection: int | None = None
) -> str:
    params: dict = {"limit": limit}
    if search is not None:
        params["search"] = search
    if collection is not None:
        params["collection"] = collection
    resp = request("GET", "/media/images/", params=params)
    envelope = _write_error_envelope(resp)
    if envelope is not None:
        return envelope
    return json.dumps(resp.json(), indent=2)


@mcp_server.tool(
    name="phoxtail_images_upload",
    description=(
        "Upload a new image to the media library from a local file path. "
        "collection_id: optional collection to place the image in "
        "(use phoxtail_collections_list to find ids). "
        "Returns {id, title, description, collection_id, file_url} "
        "of the created image."
    ),
)
def upload_image(file_path: str, title: str, collection_id: int | None = None) -> str:
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

    form_data: dict = {"title": title}
    if collection_id is not None:
        form_data["collection_id"] = str(collection_id)

    with path.open("rb") as f:
        resp = httpx.post(
            url("/api/content/v1/media/images/"),
            files={"file": (path.name, f, mime)},
            data=form_data,
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
        "Fetch a single image by its numeric ID. "
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
        "Fetch an image by numeric ID and return its visual content directly. "
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
        "Update an image's metadata by numeric ID. All fields are optional; "
        "omitted fields are left untouched. "
        "`title` renames the image. "
        "`description` is the alt-text/caption. "
        "`tags` is a full replacement list (pass [] to clear all tags). "
        "`focal_point` is {x, y, width, height} in pixels relative to the full stored "
        "image — always call `phoxtail_images_get` first to obtain the real `width` "
        "and `height`, then scale your coordinates accordingly. "
        "Do NOT estimate dimensions from the rendered view returned by `phoxtail_images_view`. "
        "`collection_id` moves the image into a different collection "
        "(use phoxtail_collections_list to find collection ids)."
    ),
)
def update_image(
    image_id: int,
    title: str | None = None,
    description: str | None = None,
    tags: list[str] | None = None,
    focal_point: dict | None = None,
    collection_id: int | None = None,
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
    if collection_id is not None:
        payload["collection_id"] = collection_id
    resp = request("PATCH", f"/media/images/{image_id}/", json_body=payload)
    envelope = _write_error_envelope(resp)
    if envelope is not None:
        return envelope
    return json.dumps(resp.json(), indent=2)


@mcp_server.tool(
    name="phoxtail_images_delete",
    description=(
        "Permanently delete an image by its numeric ID. "
        "This cannot be undone. Returns {deleted: true, id: <id>} on success."
    ),
)
def delete_image(image_id: int) -> str:
    resp = request("DELETE", f"/media/images/{image_id}/")
    envelope = _write_error_envelope(resp)
    if envelope is not None:
        return envelope
    return json.dumps({"deleted": True, "id": image_id})


# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------


@mcp_server.tool(
    name="phoxtail_pages_list_documents",
    description=(
        "Search documents in the media library by title. Returns a list of "
        "{id, title, tags, file_size, filename, file_extension, file_url, collection_id}. "
        "Pass collection= to filter by a specific collection id "
        "(use phoxtail_collections_list to browse collections). "
        "The integer `id` is the value to pass wherever a block or page field "
        "expects a Document FK."
    ),
)
def list_documents(
    search: str | None = None, limit: int = 50, collection: int | None = None
) -> str:
    params: dict = {"limit": limit}
    if search is not None:
        params["search"] = search
    if collection is not None:
        params["collection"] = collection
    resp = request("GET", "/media/documents/", params=params)
    envelope = _write_error_envelope(resp)
    if envelope is not None:
        return envelope
    return json.dumps(resp.json(), indent=2)


@mcp_server.tool(
    name="phoxtail_documents_get",
    description=(
        "Fetch a single document by its numeric ID. "
        "Returns {id, title, description, tags, file_size, filename, "
        "file_extension, file_url, collection_id}."
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
        "Upload a new document to the media library from a local file path. "
        "description: optional free-text description of the document. "
        "collection_id: optional collection to place the document in. "
        "Returns {id, title, description, filename, file_extension, "
        "collection_id, file_url} of the created document."
    ),
)
def upload_document(
    file_path: str,
    title: str,
    description: str = "",
    collection_id: int | None = None,
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

    form_data: dict = {"title": title, "description": description}
    if collection_id is not None:
        form_data["collection_id"] = str(collection_id)

    with path.open("rb") as f:
        resp = httpx.post(
            url("/api/content/v1/media/documents/"),
            files={"file": (path.name, f, mime)},
            data=form_data,
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
        "Update a document's metadata by numeric ID. All fields are optional; "
        "omitted fields are left untouched. "
        "`title` renames the document. "
        "`description` is a free-text description of the document. "
        "`tags` is a full replacement list (pass [] to clear all tags). "
        "`collection_id` moves the document into a different collection."
    ),
)
def update_document(
    document_id: int,
    title: str | None = None,
    description: str | None = None,
    tags: list[str] | None = None,
    collection_id: int | None = None,
) -> str:
    payload: dict = {}
    if title is not None:
        payload["title"] = title
    if description is not None:
        payload["description"] = description
    if tags is not None:
        payload["tags"] = tags
    if collection_id is not None:
        payload["collection_id"] = collection_id
    resp = request("PATCH", f"/media/documents/{document_id}/", json_body=payload)
    envelope = _write_error_envelope(resp)
    if envelope is not None:
        return envelope
    return json.dumps(resp.json(), indent=2)


@mcp_server.tool(
    name="phoxtail_documents_delete",
    description=(
        "Permanently delete a document by its numeric ID. "
        "This cannot be undone. Returns {deleted: true, id: <id>} on success."
    ),
)
def delete_document(document_id: int) -> str:
    resp = request("DELETE", f"/media/documents/{document_id}/")
    envelope = _write_error_envelope(resp)
    if envelope is not None:
        return envelope
    return json.dumps({"deleted": True, "id": document_id})


# ---------------------------------------------------------------------------
# Videos
# ---------------------------------------------------------------------------


@mcp_server.tool(
    name="phoxtail_videos_list",
    description=(
        "Search videos in the media library by title. "
        "Returns a list of {id, title, duration, width, height, tags, file_url, thumbnail_url, collection_id}. "
        "Pass collection= to filter by a specific collection id. "
        "The integer `id` is the value to pass wherever a block or page field expects a Video FK."
    ),
)
def list_videos(
    search: str | None = None, limit: int = 50, collection: int | None = None
) -> str:
    params: dict = {"limit": limit}
    if search is not None:
        params["search"] = search
    if collection is not None:
        params["collection"] = collection
    resp = request("GET", "/media/videos/", params=params)
    envelope = _write_error_envelope(resp)
    if envelope is not None:
        return envelope
    return json.dumps(resp.json(), indent=2)


@mcp_server.tool(
    name="phoxtail_videos_get",
    description=(
        "Fetch a single video by its numeric ID. "
        "Returns {id, title, description, duration, width, height, tags, "
        "file_url, thumbnail_url, collection_id}."
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
        "Upload a new video to the media library from a local file path. "
        "`duration` is in seconds (float). `width` and `height` are pixel dimensions "
        "and are optional but recommended. "
        "Returns {id, title, duration, width, height, file_url} of the created video."
    ),
)
def upload_video(
    file_path: str,
    title: str,
    description: str = "",
    duration: float = 0.0,
    width: int | None = None,
    height: int | None = None,
    collection_id: int | None = None,
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

    data: dict = {"title": title, "duration": str(duration), "description": description}
    if width is not None:
        data["width"] = str(width)
    if height is not None:
        data["height"] = str(height)
    if collection_id is not None:
        data["collection_id"] = str(collection_id)

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
        "Update a video's metadata by numeric ID. All fields are optional; "
        "omitted fields are left untouched. "
        "`duration` is in seconds. `width` and `height` are pixel dimensions. "
        "`tags` is a full replacement list (pass [] to clear all tags). "
        "`collection_id` moves the video into a different collection."
    ),
)
def update_video(
    video_id: int,
    title: str | None = None,
    description: str | None = None,
    tags: list[str] | None = None,
    duration: float | None = None,
    width: int | None = None,
    height: int | None = None,
    collection_id: int | None = None,
) -> str:
    payload: dict = {}
    if title is not None:
        payload["title"] = title
    if description is not None:
        payload["description"] = description
    if tags is not None:
        payload["tags"] = tags
    if duration is not None:
        payload["duration"] = duration
    if width is not None:
        payload["width"] = width
    if height is not None:
        payload["height"] = height
    if collection_id is not None:
        payload["collection_id"] = collection_id
    resp = request("PATCH", f"/media/videos/{video_id}/", json_body=payload)
    envelope = _write_error_envelope(resp)
    if envelope is not None:
        return envelope
    return json.dumps(resp.json(), indent=2)


@mcp_server.tool(
    name="phoxtail_videos_delete",
    description=(
        "Permanently delete a video by its numeric ID. "
        "This cannot be undone. Returns {deleted: true, id: <id>} on success."
    ),
)
def delete_video(video_id: int) -> str:
    resp = request("DELETE", f"/media/videos/{video_id}/")
    envelope = _write_error_envelope(resp)
    if envelope is not None:
        return envelope
    return json.dumps({"deleted": True, "id": video_id})


# ---------------------------------------------------------------------------
# Audio
# ---------------------------------------------------------------------------


@mcp_server.tool(
    name="phoxtail_audio_list",
    description=(
        "Search audio files in the media library by title. "
        "Returns a list of {id, title, duration, tags, file_url, collection_id}. "
        "Pass collection= to filter by a specific collection id. "
        "The integer `id` is the value to pass wherever a block or page field expects an Audio FK."
    ),
)
def list_audio(
    search: str | None = None, limit: int = 50, collection: int | None = None
) -> str:
    params: dict = {"limit": limit}
    if search is not None:
        params["search"] = search
    if collection is not None:
        params["collection"] = collection
    resp = request("GET", "/media/audio/", params=params)
    envelope = _write_error_envelope(resp)
    if envelope is not None:
        return envelope
    return json.dumps(resp.json(), indent=2)


@mcp_server.tool(
    name="phoxtail_audio_get",
    description=(
        "Fetch a single audio file by its numeric ID. "
        "Returns {id, title, description, duration, tags, file_url, collection_id}."
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
        "Upload a new audio file to the media library from a local file path. "
        "`duration` is in seconds (float). "
        "Returns {id, title, duration, file_url} of the created audio file."
    ),
)
def upload_audio(
    file_path: str,
    title: str,
    description: str = "",
    duration: float = 0.0,
    collection_id: int | None = None,
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

    form_data: dict = {
        "title": title,
        "duration": str(duration),
        "description": description,
    }
    if collection_id is not None:
        form_data["collection_id"] = str(collection_id)

    with path.open("rb") as f:
        resp = httpx.post(
            url("/api/content/v1/media/audio/"),
            files={"file": (path.name, f, mime)},
            data=form_data,
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
        "Update a audio file's metadata by numeric ID. All fields are optional; "
        "omitted fields are left untouched. "
        "`duration` is in seconds. "
        "`tags` is a full replacement list (pass [] to clear all tags). "
        "`collection_id` moves the audio file into a different collection."
    ),
)
def update_audio(
    audio_id: int,
    title: str | None = None,
    description: str | None = None,
    tags: list[str] | None = None,
    duration: float | None = None,
    collection_id: int | None = None,
) -> str:
    payload: dict = {}
    if title is not None:
        payload["title"] = title
    if description is not None:
        payload["description"] = description
    if tags is not None:
        payload["tags"] = tags
    if duration is not None:
        payload["duration"] = duration
    if collection_id is not None:
        payload["collection_id"] = collection_id
    resp = request("PATCH", f"/media/audio/{audio_id}/", json_body=payload)
    envelope = _write_error_envelope(resp)
    if envelope is not None:
        return envelope
    return json.dumps(resp.json(), indent=2)


@mcp_server.tool(
    name="phoxtail_audio_delete",
    description=(
        "Permanently delete a audio file by its numeric ID. "
        "This cannot be undone. Returns {deleted: true, id: <id>} on success."
    ),
)
def delete_audio(audio_id: int) -> str:
    resp = request("DELETE", f"/media/audio/{audio_id}/")
    envelope = _write_error_envelope(resp)
    if envelope is not None:
        return envelope
    return json.dumps({"deleted": True, "id": audio_id})
