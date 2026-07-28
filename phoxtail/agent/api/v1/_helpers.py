"""Internal utilities for the agent v1 API.

Resolvers (uuid → instance or 404), response serializers, and the weak
ETag machinery used for optimistic concurrency on writes.
"""

from __future__ import annotations

import hashlib
from uuid import UUID

from ninja.errors import HttpError

from phoxtail.agent.models import AgentSiteSetting, InferenceProvider, ModelArtifact

# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------


def narrow_by_search(qs, query: str):
    """Restrict ``qs`` to the rows Wagtail autocomplete matches.

    ``autocomplete()`` returns ``SearchResults``, which drops the
    queryset's ordering, ``select_related`` and annotations. Feeding the
    matched pks back through the original queryset keeps all three, at
    the cost of one extra query.
    """
    from wagtail.search.backends import get_search_backend

    matched = get_search_backend().autocomplete(query, qs)
    return qs.filter(pk__in=[obj.pk for obj in matched])


# ---------------------------------------------------------------------------
# Resolvers
# ---------------------------------------------------------------------------


def resolve_provider(uuid: UUID) -> InferenceProvider:
    try:
        return InferenceProvider.objects.get(uuid=uuid)
    except InferenceProvider.DoesNotExist:
        raise HttpError(404, f"Provider {uuid} not found.")


def resolve_artifact(uuid: UUID) -> ModelArtifact:
    try:
        return ModelArtifact.objects.select_related("provider", "permission__content_type").get(uuid=uuid)
    except ModelArtifact.DoesNotExist:
        raise HttpError(404, f"Model artifact {uuid} not found.")


def resolve_site(site_id: int):
    from wagtail.models import Site

    try:
        return Site.objects.get(pk=site_id)
    except Site.DoesNotExist:
        raise HttpError(404, f"Site {site_id} not found.")


def resolve_agent_setting(site_id: int) -> AgentSiteSetting:
    """Get (or auto-create) the agent settings record for a site."""
    return AgentSiteSetting.for_site(resolve_site(site_id))


def resolve_permission(label: str):
    """Resolve an ``"app_label.codename"`` string to a ``Permission``.

    An unparseable or unknown string is a payload problem, not a missing
    resource, so it surfaces as 422 alongside every other field-level
    validation failure.
    """
    from django.contrib.auth.models import Permission

    app_label, _, codename = label.partition(".")
    if not app_label or not codename:
        raise HttpError(422, f"Permission '{label}' must be in 'app_label.codename' form.")
    try:
        return Permission.objects.select_related("content_type").get(
            content_type__app_label=app_label,
            codename=codename,
        )
    except Permission.DoesNotExist:
        raise HttpError(422, f"Permission '{label}' does not exist.")


# ---------------------------------------------------------------------------
# Serializers
# ---------------------------------------------------------------------------


def permission_label(permission) -> str | None:
    """``"app_label.codename"`` for a Permission, or None."""
    if permission is None:
        return None
    return f"{permission.content_type.app_label}.{permission.codename}"


def provider_ref(provider: InferenceProvider) -> dict:
    return {
        "uuid": provider.uuid,
        "identifier": provider.identifier,
        "display_name": provider.display_name,
    }


def provider_detail(provider: InferenceProvider) -> dict:
    # ``artifact_count`` comes from an annotation on list queries and from a
    # COUNT on single-object ones, so listing N providers stays one query.
    count = getattr(provider, "artifact_count", None)
    return {
        **provider_ref(provider),
        "model_prefix": provider.model_prefix,
        "base_url": provider.base_url,
        "api_key_env_var": provider.api_key_env_var,
        "is_active": provider.is_active,
        "artifact_count": provider.artifacts.count() if count is None else count,
        "created_at": provider.created_at,
        "updated_at": provider.updated_at,
    }


def artifact_detail(artifact: ModelArtifact) -> dict:
    return {
        "uuid": artifact.uuid,
        "identifier": artifact.identifier,
        "display_name": artifact.display_name,
        "provider": provider_ref(artifact.provider),
        "permission": permission_label(artifact.permission),
        "is_active": artifact.is_active,
        "sort_order": artifact.sort_order or 0,
        "created_at": artifact.created_at,
        "updated_at": artifact.updated_at,
    }


def agent_setting_detail(setting: AgentSiteSetting) -> dict:
    artifact = setting.default_artifact
    return {
        "site_id": setting.site_id,
        "default_artifact": artifact_detail(artifact) if artifact else None,
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


def provider_etag(provider: InferenceProvider) -> str:
    """Compute a weak ETag covering all mutable provider fields."""
    return _hash_parts(
        provider.identifier,
        provider.display_name,
        provider.model_prefix,
        provider.base_url,
        provider.api_key_env_var,
        str(provider.is_active),
    )


def artifact_etag(artifact: ModelArtifact) -> str:
    """Compute a weak ETag covering all mutable artifact fields.

    ``sort_order`` is included because it is writable: two agents
    reordering the picker concurrently must collide rather than have the
    later write silently win.
    """
    return _hash_parts(
        str(artifact.provider_id),
        artifact.identifier,
        artifact.display_name,
        str(artifact.permission_id or ""),
        str(artifact.is_active),
        str(artifact.sort_order or 0),
    )


def agent_setting_etag(setting: AgentSiteSetting) -> str:
    return _hash_parts(str(setting.site_id), str(setting.default_artifact_id or ""))


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
