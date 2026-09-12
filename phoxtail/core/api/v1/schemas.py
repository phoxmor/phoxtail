"""Schemas for the core API.

Moved verbatim from the content domain when core took ownership of its own
surface: ``InternalLink`` is a core model, not a Wagtail entity.
"""

from __future__ import annotations

from ninja import Schema


class InternalLinkItem(Schema):
    id: int
    uuid: str
    label: str
    url_name: str
    url: str
    created_at: str
    updated_at: str


class InternalLinkList(Schema):
    items: list[InternalLinkItem]
    total: int


class InternalLinkCreate(Schema):
    label: str
    url_name: str


class InternalLinkPatch(Schema):
    label: str | None = None
    url_name: str | None = None


class Error(Schema):
    detail: str
    title: str | None = None
