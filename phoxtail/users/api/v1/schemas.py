"""Pydantic v2 schemas for the users v1 API.

These schemas are the stable contract for every consumer of the API —
the Phoxtail MCP server, the in-house chatbot, and any future client.
Field names and shapes here are breaking-change territory: any change
forces a v2.

Identity convention: resources are addressed by ``uuid`` everywhere in
the public contract. Numeric database PKs are never exposed.
"""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from ninja import Field, Schema


class Error(Schema):
    detail: str


# ---------------------------------------------------------------------------
# Genders
# ---------------------------------------------------------------------------


class GenderRef(Schema):
    """Minimal embed of a gender, used inside user responses."""

    uuid: UUID
    name: str


class Gender(GenderRef):
    """Detail-view shape for a Gender."""

    symbol: str | None = None
    created_at: datetime | None = None
    updated_at: datetime


class GenderList(Schema):
    genders: list[Gender]
    total: int


class GenderCreate(Schema):
    """Request body for ``POST /genders/``."""

    name: str
    symbol: str | None = None


class GenderUpdate(Schema):
    """Request body for ``PATCH /genders/{uuid}/``.

    Partial-update semantics: only fields present in the request are
    applied. ``symbol`` accepts explicit ``null`` to clear it; ``name``
    ignores ``null``.
    """

    name: str | None = None
    symbol: str | None = None


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------


class UserSummary(Schema):
    """List-view shape for a User."""

    uuid: UUID
    email: str
    username: str
    first_name: str
    last_name: str
    full_name: str
    is_active: bool


class User(UserSummary):
    """Detail-view shape for a User. Adds profile, gender and login metadata."""

    born_at: date | None = None
    age_display: str | None = None
    gender: GenderRef | None = None
    country: str | None = Field(None, description="ISO 3166-1 alpha-2 country code.")
    country_name: str | None = None
    phone_number: str | None = Field(None, description="E.164 format.")
    date_joined: datetime
    last_login: datetime | None = None
    email_verified: bool = Field(description="Whether the allauth email record is verified.")
    is_superuser: bool = Field(description="Read-only context flag — never writable through this API.")


class UserList(Schema):
    users: list[UserSummary]
    total: int


class UserCreate(Schema):
    """Request body for ``POST /users/`` and rows of ``POST /users/bulk/``.

    Deliberately has **no password field**: agents must never transport
    passwords. Users are created with an unusable password and no login
    access; activation flows are a separate concern.
    """

    email: str
    first_name: str
    last_name: str
    username: str | None = Field(None, description="Lowercase. Omit to auto-generate from the name/email.")
    born_at: date | None = Field(None, description="ISO date, e.g. '1990-04-23'.")
    gender_uuid: UUID | None = None
    country: str | None = Field(None, description="ISO 3166-1 alpha-2 country code, e.g. 'GR'.")
    phone_number: str | None = Field(None, description="E.164 format, e.g. '+306912345678'.")
    is_active: bool = True


class UserUpdate(Schema):
    """Request body for ``PATCH /users/{uuid}/``.

    Partial-update semantics: only fields present in the request are
    applied. ``born_at``, ``gender_uuid``, ``country`` and ``phone_number``
    accept explicit ``null`` to clear the value; every other field ignores
    ``null``. ``is_superuser``, ``is_staff`` and ``password`` are never
    writable.
    """

    first_name: str | None = None
    last_name: str | None = None
    email: str | None = None
    username: str | None = None
    born_at: date | None = None
    gender_uuid: UUID | None = None
    country: str | None = None
    phone_number: str | None = None
    is_active: bool | None = None


# ---------------------------------------------------------------------------
# Email verification
# ---------------------------------------------------------------------------


class EmailVerification(Schema):
    """Response of ``POST /users/{uuid}/verify-email/``."""

    uuid: UUID
    email: str
    status: str = Field(description="'verified' or 'already_verified'.")


class EmailVerificationBulk(Schema):
    """Request body for ``POST /users/verify-emails/``."""

    user_uuids: list[UUID]


class EmailVerificationRowResult(Schema):
    """Per-row outcome of a bulk verification — rows are independent."""

    index: int
    uuid: UUID
    status: str = Field(description="'verified', 'already_verified' or 'error'.")
    email: str | None = None
    detail: str | None = None


class EmailVerificationBulkResult(Schema):
    results: list[EmailVerificationRowResult]
    verified: int
    already_verified: int
    failed: int


# ---------------------------------------------------------------------------
# Bulk creation
# ---------------------------------------------------------------------------


class UserBulkCreate(Schema):
    """Request body for ``POST /users/bulk/``."""

    users: list[UserCreate]


class UserBulkRowResult(Schema):
    """Per-row outcome of a bulk create — rows are independent."""

    index: int
    status: str = Field(description="'created' or 'error'.")
    uuid: UUID | None = None
    email: str
    detail: str | None = None


class UserBulkResult(Schema):
    results: list[UserBulkRowResult]
    created: int
    failed: int
