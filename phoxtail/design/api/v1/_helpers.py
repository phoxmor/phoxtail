"""Shared resolution, serialization, and ETag helpers for design v1."""

from __future__ import annotations

import hashlib

from ninja.errors import HttpError

# ---------------------------------------------------------------------------
# ETag utilities
# ---------------------------------------------------------------------------


def _strip_weak(tag: str) -> str:
    return tag[2:] if tag.startswith("W/") else tag


def etag_matches(header_value: str | None, current: str) -> bool:
    if not header_value:
        return False
    candidates = {t.strip() for t in header_value.split(",")}
    return "*" in candidates or _strip_weak(current) in {_strip_weak(t) for t in candidates}


def _hash(*parts: str) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update(p.encode("utf-8"))
        h.update(b"\x00")
    return f'W/"{h.hexdigest()[:16]}"'


def palette_set_etag(ps) -> str:
    return _hash(
        str(ps.pk),
        ps.name,
        ps.identifier,
        ps.description,
        ps.updated_at.isoformat(),
    )


def palette_etag(p) -> str:
    shades = "".join(getattr(p, f"shade_{s}") or "" for s in (50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 950))
    return _hash(
        str(p.pk),
        str(p.palette_set_id),
        p.title,
        p.description,
        shades,
        p.updated_at.isoformat(),
    )


def palette_role_etag(r) -> str:
    return _hash(str(r.pk), r.name, r.identifier, r.description)


def font_family_etag(ff) -> str:
    return _hash(
        str(ff.pk),
        ff.name,
        ff.description,
        ff.category,
        ff.fallback,
        ff.updated_at.isoformat(),
    )


def font_role_etag(r) -> str:
    return _hash(str(r.pk), r.name, r.identifier, r.description)


def font_weight_etag(w) -> str:
    return _hash(
        str(w.pk),
        str(w.family_id),
        str(w.weight),
        w.style,
        w.file.name if w.file else "",
        w.updated_at.isoformat(),
    )


# ---------------------------------------------------------------------------
# Resolution helpers
# ---------------------------------------------------------------------------


def resolve_palette_set(pk: int):
    from phoxtail.design.models import PaletteSet

    try:
        return PaletteSet.objects.get(pk=pk)
    except PaletteSet.DoesNotExist:
        raise HttpError(404, f"PaletteSet {pk} not found.")


def resolve_palette(pk: int):
    from phoxtail.design.models import Palette

    try:
        return Palette.objects.select_related("palette_set").get(pk=pk)
    except Palette.DoesNotExist:
        raise HttpError(404, f"Palette {pk} not found.")


def resolve_palette_role(pk: int):
    from phoxtail.design.models import PaletteRole

    try:
        return PaletteRole.objects.get(pk=pk)
    except PaletteRole.DoesNotExist:
        raise HttpError(404, f"PaletteRole {pk} not found.")


def resolve_font_family(pk: int):
    from phoxtail.design.models import FontFamily

    try:
        return FontFamily.objects.get(pk=pk)
    except FontFamily.DoesNotExist:
        raise HttpError(404, f"FontFamily {pk} not found.")


def resolve_font_role(pk: int):
    from phoxtail.design.models import FontRole

    try:
        return FontRole.objects.get(pk=pk)
    except FontRole.DoesNotExist:
        raise HttpError(404, f"FontRole {pk} not found.")


def resolve_font_weight(pk: int):
    from phoxtail.design.models import FontWeight

    try:
        return FontWeight.objects.select_related("family").get(pk=pk)
    except FontWeight.DoesNotExist:
        raise HttpError(404, f"FontWeight {pk} not found.")


# ---------------------------------------------------------------------------
# If-Match enforcement
# ---------------------------------------------------------------------------


def require_if_match(request, current_etag: str) -> None:

    if_match = request.headers.get("If-Match")
    if not if_match:
        raise HttpError(
            428,
            "If-Match header is required. Fetch the resource first and pass the ETag from the response.",
        )
    if not etag_matches(if_match, current_etag):
        raise HttpError(
            412,
            "ETag mismatch: the resource has changed since you last read it. Re-fetch and retry.",
        )
