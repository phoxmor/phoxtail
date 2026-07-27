"""``phoxtail_font_weights_*`` MCP tools for font weight management."""

from __future__ import annotations

import json
import mimetypes
from pathlib import Path

import httpx

from phoxtail.mcp import mcp_server
from phoxtail.mcp._http import outbound_token, url
from phoxtail.mcp.design._error import error_envelope
from phoxtail.mcp.design._http import request

# The MCP server runs inside the Docker container (WORKDIR /app), but agents
# run on the host. In dev mode the project root is bind-mounted at /app, so a
# path relative to the project root resolves identically on both sides.
# Agents should stage upload files under .phoxtail/mcp/uploads/ and pass the
# relative path; this helper falls back to /app/<path> when the literal path
# doesn't exist (i.e. the agent passed a host-relative path from inside the container).
_CONTAINER_ROOT = Path("/app")

_UPLOAD_HINT = "Stage the file under .phoxtail/mcp/uploads/ and pass the relative path."


def _resolve_upload_path(file_path: str) -> Path:
    p = Path(file_path)
    if p.exists():
        return p
    candidate = _CONTAINER_ROOT / p
    if candidate.exists():
        return candidate
    return p  # let the caller produce the "not found" error


def _auth_headers() -> dict:
    token = outbound_token()
    return {"Authorization": f"Bearer {token}"} if token else {}


@mcp_server.tool(
    name="phoxtail_font_weights_list",
    description=(
        "List font weight entries. "
        "Pass `font_family_id` to filter to a specific family. "
        "Returns id, font_family_id, weight (100-900), style (normal/italic), file_url."
    ),
)
def font_weights_list(font_family_id: int | None = None) -> str:
    params: dict = {}
    if font_family_id is not None:
        params["font_family_id"] = font_family_id
    resp = request("GET", "/font-weights/", params=params)
    env = error_envelope(resp)
    if env is not None:
        return env
    return json.dumps(resp.json(), indent=2)


@mcp_server.tool(
    name="phoxtail_font_weights_get",
    description=("Get a single font weight by id. Response includes `_etag` needed for delete."),
)
def font_weights_get(weight_id: int) -> str:
    resp = request("GET", f"/font-weights/{weight_id}/")
    env = error_envelope(resp)
    if env is not None:
        return env
    data = resp.json()
    data["_etag"] = resp.headers.get("ETag", "")
    return json.dumps(data, indent=2)


@mcp_server.tool(
    name="phoxtail_font_weights_upload",
    description=(
        "Upload a font weight file (WOFF2, TTF, or OTF) for a font family. "
        "IMPORTANT: The MCP server runs inside Docker. To upload a file from your host, "
        "first copy it into the project's .phoxtail/mcp/uploads/ directory, then pass "
        "the relative path, e.g. '.phoxtail/mcp/uploads/font.woff2'. "
        "TTF and OTF files are automatically converted to WOFF2 on the server. "
        "`weight` must be a multiple of 100 between 100 and 900 "
        "(100=Thin, 300=Light, 400=Regular, 700=Bold, 900=Black). "
        "`style` is 'normal' or 'italic'. "
        "Use this after phoxtail_font_families_create to add weights."
    ),
)
def font_weights_upload(
    file_path: str,
    font_family_id: int,
    weight: int,
    style: str = "normal",
) -> str:
    path = _resolve_upload_path(file_path)
    if not path.exists():
        return json.dumps({"error": f"File not found: {file_path}. {_UPLOAD_HINT}"})

    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"

    with path.open("rb") as f:
        resp = httpx.post(
            url("/api/design/v1/font-weights/"),
            files={"file": (path.name, f, mime)},
            params={"font_family_id": font_family_id, "weight": weight, "style": style},
            headers=_auth_headers(),
            timeout=60.0,
            follow_redirects=True,
        )

    env = error_envelope(resp)
    if env is not None:
        return env
    data = resp.json()
    data["_etag"] = resp.headers.get("ETag", "")
    return json.dumps(data, indent=2)


@mcp_server.tool(
    name="phoxtail_font_weights_create_from_url",
    description=(
        "Fetch a font file from a URL and add it as a weight for a font family. "
        "Accepts https:// URLs only (SSRF-protected). Pass the direct file URL "
        "in `source_url` — not an HTML page. "
        "TTF and OTF files are automatically converted to WOFF2 on the server. "
        "Ideal for ingesting from Google Fonts CDN or other font CDN URLs. "
        "`weight` must be a multiple of 100 between 100 and 900. "
        "`style` is 'normal' or 'italic'."
    ),
)
def font_weights_create_from_url(
    font_family_id: int,
    weight: int,
    source_url: str,
    style: str = "normal",
) -> str:
    resp = request(
        "POST",
        "/font-weights/from-url/",
        params={
            "font_family_id": font_family_id,
            "weight": weight,
            "style": style,
            "url": source_url,
        },
    )
    env = error_envelope(resp)
    if env is not None:
        return env
    data = resp.json()
    data["_etag"] = resp.headers.get("ETag", "")
    return json.dumps(data, indent=2)


@mcp_server.tool(
    name="phoxtail_font_weights_delete",
    description=(
        "Delete a font weight entry and its file. "
        "Requires `etag` from phoxtail_font_weights_get. "
        "To delete an entire family with all weights use phoxtail_font_families_delete."
    ),
)
def font_weights_delete(weight_id: int, etag: str) -> str:
    resp = request(
        "DELETE",
        f"/font-weights/{weight_id}/",
        headers={"If-Match": etag},
    )
    env = error_envelope(resp)
    if env is not None:
        return env
    return json.dumps({"deleted": weight_id})
