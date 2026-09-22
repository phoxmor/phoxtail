"""Pydantic v2 schemas for the agent v1 configuration API.

These schemas are the stable contract for every consumer of the provider
catalogue — the Phoxtail MCP server, the CLI, and any future client.
Field names and shapes here are the contract. Until phoxtail reaches 1.0 a
breaking change stays in v1 and is announced in the changelog; from 1.0 on,
one forces a v2.

Identity convention: resources are addressed by ``uuid`` everywhere in
the public contract. Numeric database PKs are never exposed. The one
exception is ``site_id`` on the settings resource, which mirrors Wagtail's
own site addressing used by ``/api/cms/v1/site-settings/``.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from ninja import Schema


class Error(Schema):
    detail: str


# ---------------------------------------------------------------------------
# Providers
# ---------------------------------------------------------------------------


class ProviderRef(Schema):
    """Minimal embed of a provider, used inside artifact responses."""

    uuid: UUID
    identifier: str
    display_name: str


class Provider(ProviderRef):
    """Detail-view shape for an InferenceProvider."""

    model_prefix: str
    base_url: str
    api_key_env_var: str
    is_active: bool
    artifact_count: int
    created_at: datetime | None = None
    updated_at: datetime

    @staticmethod
    def resolve_artifact_count(provider) -> int:
        # Annotated onto list queries, so listing N providers stays one
        # query; counted on single-object ones.
        count = getattr(provider, "artifact_count", None)
        return provider.artifacts.count() if count is None else count


class ProviderCreate(Schema):
    """Request body for ``POST /providers/``."""

    identifier: str
    display_name: str
    model_prefix: str = ""
    base_url: str = ""
    api_key_env_var: str = ""
    is_active: bool = True


class ProviderUpdate(Schema):
    """Request body for ``PATCH /providers/{uuid}/``.

    Partial-update semantics: only fields present in the request are
    applied.
    """

    identifier: str | None = None
    display_name: str | None = None
    model_prefix: str | None = None
    base_url: str | None = None
    api_key_env_var: str | None = None
    is_active: bool | None = None


# ---------------------------------------------------------------------------
# Artifacts
# ---------------------------------------------------------------------------


class Artifact(Schema):
    """Detail-view shape for a ModelArtifact."""

    uuid: UUID
    identifier: str
    display_name: str
    provider: ProviderRef
    permission: str | None = None
    is_active: bool
    sort_order: int
    created_at: datetime | None = None
    updated_at: datetime

    @staticmethod
    def resolve_permission(artifact) -> str | None:
        permission = artifact.permission
        if permission is None:
            return None
        return f"{permission.content_type.app_label}.{permission.codename}"

    @staticmethod
    def resolve_sort_order(artifact) -> int:
        return artifact.sort_order or 0


class ArtifactCreate(Schema):
    """Request body for ``POST /artifacts/``."""

    provider_uuid: UUID
    identifier: str
    display_name: str
    permission: str | None = None
    is_active: bool = True
    sort_order: int = 0


class ArtifactUpdate(Schema):
    """Request body for ``PATCH /artifacts/{uuid}/``.

    ``permission`` accepts explicit ``null`` to clear the gate, making the
    model visible to everyone who can reach the chatbot.
    """

    provider_uuid: UUID | None = None
    identifier: str | None = None
    display_name: str | None = None
    permission: str | None = None
    is_active: bool | None = None
    sort_order: int | None = None


# ---------------------------------------------------------------------------
# Site settings
# ---------------------------------------------------------------------------


class AgentSettings(Schema):
    """Detail-view shape for AgentSiteSetting."""

    site_id: int
    default_artifact: Artifact | None = None


class AgentSettingsUpdate(Schema):
    """Request body for ``PATCH /settings/{site_id}/``.

    ``default_artifact_uuid`` accepts explicit ``null`` to unset the
    default, which leaves users having to pick a model per conversation.
    """

    default_artifact_uuid: UUID | None = None
