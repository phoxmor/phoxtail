"""Schemas for the core API: the internal links core owns.

``InternalLink`` is a core model, not a Wagtail entity, so it has its own
surface rather than living under cms.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from ninja import Schema


class InternalLinkItem(Schema):
    id: int
    uuid: UUID
    label: str
    url_name: str
    url: str
    created_at: datetime | None = None
    updated_at: datetime


class InternalLinkCreate(Schema):
    label: str
    url_name: str


class InternalLinkPatch(Schema):
    label: str | None = None
    url_name: str | None = None


class Error(Schema):
    detail: str
    title: str | None = None
