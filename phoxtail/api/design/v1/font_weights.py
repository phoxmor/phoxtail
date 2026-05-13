"""``/api/design/v1/font-weights/`` — FontWeight upload and management."""

from __future__ import annotations

import io
import ipaddress
import socket
from pathlib import PurePosixPath
from urllib.parse import urlparse

from django.core.files.base import ContentFile
from django.http import HttpRequest, HttpResponse
from ninja import File, Query, Router, Schema, UploadedFile
from ninja.errors import HttpError

from phoxtail.api.design.v1._helpers import (
    font_weight_etag,
    font_weight_summary,
    require_if_match,
    resolve_font_family,
    resolve_font_weight,
)

router = Router()

_MAX_URL_BYTES = 5 * 1024 * 1024  # 5 MB

# Magic bytes for font format detection
_WOFF2_MAGIC = b"wOF2"
_OTF_MAGIC = b"OTTO"
_TTF_MAGIC = b"\x00\x01\x00\x00"


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class FontWeightSummary(Schema):
    id: int
    font_family_id: int
    font_family_name: str
    weight: int
    style: str
    file_url: str | None
    file_name: str | None
    created_at: str | None
    updated_at: str


class FontWeightList(Schema):
    font_weights: list[FontWeightSummary]
    total: int


class Error(Schema):
    detail: str


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _detect_format(data: bytes) -> str | None:
    """Return 'woff2', 'otf', 'ttf', or None."""
    if data[:4] == _WOFF2_MAGIC:
        return "woff2"
    if data[:4] == _OTF_MAGIC:
        return "otf"
    if data[:4] == _TTF_MAGIC:
        return "ttf"
    return None


def _convert_to_woff2(data: bytes) -> bytes:
    """Convert TTF/OTF bytes to WOFF2 using fonttools."""
    try:
        from fontTools.ttLib.woff2 import compress
    except ImportError:
        raise HttpError(500, "fonttools[woff] is not installed on this server.")

    in_buf = io.BytesIO(data)
    out_buf = io.BytesIO()
    compress(in_buf, out_buf)
    return out_buf.getvalue()


def _ensure_woff2(data: bytes) -> bytes:
    """Return WOFF2 bytes — convert from TTF/OTF if needed."""
    fmt = _detect_format(data)
    if fmt is None:
        raise HttpError(400, "Unrecognised font format. Supply WOFF2, TTF, or OTF.")
    if fmt == "woff2":
        return data
    return _convert_to_woff2(data)


_PRIVATE_NETS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]


def _ssrf_guard(font_url: str) -> None:
    """Raise HttpError 400 if the URL is unsafe to fetch."""
    parsed = urlparse(font_url)
    if parsed.scheme != "https":
        raise HttpError(400, "Only https:// URLs are accepted.")
    host = parsed.hostname
    if not host:
        raise HttpError(400, "URL has no hostname.")
    try:
        resolved_ip = ipaddress.ip_address(socket.gethostbyname(host))
    except (socket.gaierror, ValueError):
        raise HttpError(400, f"Could not resolve hostname: {host}")
    for net in _PRIVATE_NETS:
        if resolved_ip in net:
            raise HttpError(400, "URL resolves to a private or loopback address.")


def _fetch_url(font_url: str) -> bytes:
    """Fetch font bytes from a URL, enforcing SSRF guard and size cap."""
    import httpx

    _ssrf_guard(font_url)
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
    }
    chunks: list[bytes] = []
    total = 0
    try:
        with httpx.stream("GET", font_url, headers=headers, follow_redirects=True, timeout=30.0) as resp:
            try:
                resp.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise HttpError(400, f"Remote returned {exc.response.status_code} for URL.")
            for chunk in resp.iter_bytes(chunk_size=65536):
                total += len(chunk)
                if total > _MAX_URL_BYTES:
                    limit_mb = _MAX_URL_BYTES // 1024 // 1024
                    raise HttpError(400, f"Font file exceeds {limit_mb} MB limit.")
                chunks.append(chunk)
    except (httpx.ConnectError, httpx.TimeoutException) as exc:
        raise HttpError(400, f"Could not fetch URL: {exc}")
    return b"".join(chunks)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/", response={200: FontWeightList}, summary="List font weights")
def list_font_weights(
    request: HttpRequest,
    font_family_id: int | None = Query(None, description="Filter by font family."),
):
    from phoxtail.design.models import FontWeight

    qs = FontWeight.objects.select_related("family").order_by("family__name", "weight", "style")
    if font_family_id is not None:
        qs = qs.filter(family_id=font_family_id)
    items = [font_weight_summary(w) for w in qs]
    return {"font_weights": items, "total": len(items)}


@router.get(
    "/{weight_id}/",
    response={200: FontWeightSummary, 404: Error},
    summary="Get a font weight",
)
def get_font_weight(request: HttpRequest, response: HttpResponse, weight_id: int):
    w = resolve_font_weight(weight_id)
    response["ETag"] = font_weight_etag(w)
    return font_weight_summary(w)


@router.post(
    "/",
    response={201: FontWeightSummary, 400: Error, 409: Error},
    summary="Upload a font weight file",
)
def upload_font_weight(
    request: HttpRequest,
    response: HttpResponse,
    font_family_id: int,
    weight: int,
    style: str,
    file: UploadedFile = File(...),
):
    """Upload a WOFF2, TTF, or OTF file. TTF/OTF are converted to WOFF2 server-side."""
    from django.db import IntegrityError

    from phoxtail.design.models import FontWeight

    if style not in ("normal", "italic"):
        raise HttpError(400, "style must be 'normal' or 'italic'.")
    if not (100 <= weight <= 900 and weight % 100 == 0):
        raise HttpError(400, "weight must be a multiple of 100 between 100 and 900.")

    family = resolve_font_family(font_family_id)
    data = file.read()
    woff2_data = _ensure_woff2(data)

    stem = PurePosixPath(file.name).stem if file.name else f"{family.name}-{weight}"
    filename = f"{stem}.woff2"

    try:
        fw = FontWeight(family=family, weight=weight, style=style)
        fw.file.save(filename, ContentFile(woff2_data), save=True)
    except IntegrityError:
        raise HttpError(
            409,
            f"A {weight} {style} weight for '{family.name}' already exists.",
        )

    fw.refresh_from_db()
    response["ETag"] = font_weight_etag(fw)
    return 201, font_weight_summary(fw)


@router.post(
    "/from-url/",
    response={201: FontWeightSummary, 400: Error, 409: Error},
    summary="Ingest a font weight from a URL",
)
def ingest_font_weight_from_url(
    request: HttpRequest,
    response: HttpResponse,
    font_family_id: int,
    weight: int,
    style: str,
    url: str,
):
    """Fetch a font file from a URL (https only). TTF/OTF are converted to WOFF2."""
    from django.db import IntegrityError

    from phoxtail.design.models import FontWeight

    if style not in ("normal", "italic"):
        raise HttpError(400, "style must be 'normal' or 'italic'.")
    if not (100 <= weight <= 900 and weight % 100 == 0):
        raise HttpError(400, "weight must be a multiple of 100 between 100 and 900.")

    family = resolve_font_family(font_family_id)
    data = _fetch_url(url)
    woff2_data = _ensure_woff2(data)

    parsed_name = PurePosixPath(urlparse(url).path).stem or f"{family.name}-{weight}"
    filename = f"{parsed_name}.woff2"

    try:
        fw = FontWeight(family=family, weight=weight, style=style)
        fw.file.save(filename, ContentFile(woff2_data), save=True)
    except IntegrityError:
        raise HttpError(
            409,
            f"A {weight} {style} weight for '{family.name}' already exists.",
        )

    fw.refresh_from_db()
    response["ETag"] = font_weight_etag(fw)
    return 201, font_weight_summary(fw)


@router.delete(
    "/{weight_id}/",
    response={204: None, 404: Error, 412: Error, 428: Error},
    summary="Delete a font weight",
)
def delete_font_weight(request: HttpRequest, weight_id: int):
    w = resolve_font_weight(weight_id)
    require_if_match(request, font_weight_etag(w))
    w.file.delete(save=False)
    w.delete()
    return 204, None
