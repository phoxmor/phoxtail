"""Pydantic v2 schemas for the dashboard v1 API.

A menu's entries travel as opaque stream data — a list of ``{type, value}``
dicts on the way in, formatted JSON on the way out — the same shape shared
block content uses. The entry types themselves are fixed
(:mod:`phoxtail.dashboard.blocks`) but their nesting is not worth restating
in a second type system.
"""

from __future__ import annotations

import json
from datetime import datetime
from uuid import UUID

from ninja import Schema


class Error(Schema):
    detail: str


class MenuSummary(Schema):
    id: int
    uuid: UUID
    site_id: int
    site_hostname: str
    locale_id: int
    language_code: str
    entry_count: int
    created_at: datetime | None = None
    updated_at: datetime

    @staticmethod
    def resolve_site_hostname(menu) -> str:
        return menu.site.hostname

    @staticmethod
    def resolve_language_code(menu) -> str:
        return menu.locale.language_code

    @staticmethod
    def resolve_entry_count(menu) -> int:
        return len(menu.items)


class Menu(MenuSummary):
    items: str

    @staticmethod
    def resolve_items(menu) -> str:
        return json.dumps(menu.items.get_prep_value() or [], indent=2)


class MenuCreate(Schema):
    """Request body for ``POST /menus/``."""

    site_id: int
    locale_id: int
    items: list[dict] = []


class MenuUpdate(Schema):
    """Request body for ``PATCH /menus/{id}/``.

    Only the entries change after creation; a menu's site and language are
    what identify it. The ETag check happens via ``If-Match``.
    """

    items: list[dict] | None = None
