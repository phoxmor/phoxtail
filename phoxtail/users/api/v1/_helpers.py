"""Internal utilities for the users v1 API.

Resolvers (uuid → instance or 404), response serializers, and the weak
ETag machinery used for optimistic concurrency on writes.
"""

from __future__ import annotations

import hashlib
from uuid import UUID

from django.contrib.auth import get_user_model
from ninja.errors import HttpError

from phoxtail.users.models import Gender

# ---------------------------------------------------------------------------
# Resolvers
# ---------------------------------------------------------------------------


def resolve_user(uuid: UUID):
    User = get_user_model()
    try:
        return User.objects.select_related("gender").get(uuid=uuid)
    except User.DoesNotExist:
        raise HttpError(404, f"User {uuid} not found.")


def resolve_gender(uuid: UUID) -> Gender:
    try:
        return Gender.objects.get(uuid=uuid)
    except Gender.DoesNotExist:
        raise HttpError(404, f"Gender {uuid} not found.")


# ---------------------------------------------------------------------------
# Serializers
# ---------------------------------------------------------------------------


def user_summary(user) -> dict:
    return {
        "uuid": user.uuid,
        "email": user.email,
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "full_name": user.get_full_name(),
        "is_active": user.is_active,
    }


def gender_ref(gender: Gender) -> dict:
    return {
        "uuid": gender.uuid,
        "name": gender.name,
    }


def user_detail(user) -> dict:
    from allauth.account.models import EmailAddress

    return {
        **user_summary(user),
        "email_verified": EmailAddress.objects.filter(user=user, email=user.email, verified=True).exists(),
        "born_at": user.born_at,
        "age_display": user.age_display,
        "gender": gender_ref(user.gender) if user.gender else None,
        "country": str(user.country) if user.country else None,
        "country_name": user.country.name if user.country else None,
        "phone_number": str(user.phone_number) if user.phone_number else None,
        "date_joined": user.date_joined,
        "last_login": user.last_login,
        "is_superuser": user.is_superuser,
    }


def gender_detail(gender: Gender) -> dict:
    return {
        "uuid": gender.uuid,
        "name": gender.name,
        "symbol": gender.symbol,
        "created_at": gender.created_at,
        "updated_at": gender.updated_at,
    }


# ---------------------------------------------------------------------------
# ETags
# ---------------------------------------------------------------------------


def _hash_parts(*parts: str) -> str:
    h = hashlib.sha256()
    for part in parts:
        h.update(part.encode("utf-8"))
        h.update(b"\x00")
    return f'W/"{h.hexdigest()[:16]}"'


def user_etag(user) -> str:
    """Compute a weak ETag covering all mutable user fields."""
    return _hash_parts(
        user.email,
        user.username,
        user.first_name,
        user.last_name,
        str(user.born_at or ""),
        str(user.gender_id or ""),
        str(user.country or ""),
        str(user.phone_number or ""),
        str(user.is_active),
    )


def gender_etag(gender: Gender) -> str:
    """Compute a weak ETag covering all mutable gender fields."""
    return _hash_parts(
        gender.name,
        gender.symbol or "",
    )


def etag_matches(header_value: str | None, current: str) -> bool:
    """Check ``If-Match`` semantics tolerantly.

    Treats ``W/"abc"`` and ``"abc"`` as equivalent, per RFC 7232: weak
    validators are acceptable on non-range update requests.
    """
    if not header_value:
        return False
    candidates = {tag.strip() for tag in header_value.split(",")}
    normalized = {_strip_weak_prefix(t) for t in candidates}
    return _strip_weak_prefix(current) in normalized or "*" in candidates


def _strip_weak_prefix(tag: str) -> str:
    return tag[2:] if tag.startswith("W/") else tag


def require_if_match(request, current_etag: str) -> None:
    """Enforce the read-before-write contract on a mutating endpoint."""
    if_match = request.headers.get("If-Match")
    if not if_match:
        raise HttpError(
            428,
            "If-Match header is required. Send the ETag from your most recent GET of this resource.",
        )
    if not etag_matches(if_match, current_etag):
        raise HttpError(
            412,
            "ETag mismatch: the resource has changed since you last read it. Re-fetch and retry.",
        )


def delete_guarded(instance) -> None:
    """Delete an instance, translating FK protection into a 409.

    Gender deletion is safe today (``User.gender`` is ``SET_NULL``), but a
    future protected relation should surface as a conflict the client can
    act on instead of a 500.
    """
    from django.db.models import ProtectedError

    try:
        instance.delete()
    except ProtectedError as exc:
        raise HttpError(
            409,
            f"Cannot delete: {len(exc.protected_objects)} related object(s) reference it. Delete or move those first.",
        )
