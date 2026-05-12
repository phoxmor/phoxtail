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
    return "*" in candidates or _strip_weak(current) in {
        _strip_weak(t) for t in candidates
    }


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
    shades = "".join(
        getattr(p, f"shade_{s}") or ""
        for s in (50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 950)
    )
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
# Serializers
# ---------------------------------------------------------------------------


def _shades(p) -> dict:
    return {
        str(s): getattr(p, f"shade_{s}") or ""
        for s in (50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 950)
    }


def palette_set_summary(ps) -> dict:
    return {
        "id": ps.pk,
        "name": ps.name,
        "identifier": ps.identifier,
        "description": ps.description,
        "palette_count": ps._palette_count
        if hasattr(ps, "_palette_count")
        else ps.palettes.count(),
        "created_at": ps.created_at.isoformat() if ps.created_at else None,
        "updated_at": ps.updated_at.isoformat(),
    }


def palette_summary(p) -> dict:
    return {
        "id": p.pk,
        "palette_set_id": p.palette_set_id,
        "palette_set_name": p.palette_set.name if hasattr(p, "palette_set") else "",
        "title": p.title,
        "description": p.description,
        "sort_order": p.sort_order or 0,
        "shades": _shades(p),
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat(),
    }


def palette_role_summary(r) -> dict:
    return {
        "id": r.pk,
        "name": r.name,
        "identifier": r.identifier,
        "description": r.description,
    }


def font_family_summary(ff) -> dict:
    return {
        "id": ff.pk,
        "name": ff.name,
        "description": ff.description,
        "category": ff.category,
        "fallback": ff.fallback,
        "weight_count": ff._weight_count
        if hasattr(ff, "_weight_count")
        else ff.weights.count(),
        "created_at": ff.created_at.isoformat() if ff.created_at else None,
        "updated_at": ff.updated_at.isoformat(),
    }


def font_role_summary(r) -> dict:
    return {
        "id": r.pk,
        "name": r.name,
        "identifier": r.identifier,
        "description": r.description,
    }


def font_weight_summary(w) -> dict:
    return {
        "id": w.pk,
        "font_family_id": w.family_id,
        "font_family_name": w.family.name if hasattr(w, "family") else "",
        "weight": w.weight,
        "style": w.style,
        "file_url": w.file.url if w.file else None,
        "file_name": w.file.name if w.file else None,
        "created_at": w.created_at.isoformat() if w.created_at else None,
        "updated_at": w.updated_at.isoformat(),
    }


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
            "If-Match header is required. Fetch the resource first and pass "
            "the ETag from the response.",
        )
    if not etag_matches(if_match, current_etag):
        raise HttpError(
            412,
            "ETag mismatch: the resource has changed since you last read it. "
            "Re-fetch and retry.",
        )
