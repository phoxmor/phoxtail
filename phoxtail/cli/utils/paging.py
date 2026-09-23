"""How the CLI titles one page of a paged list."""

from __future__ import annotations

from typing import Any


def page_title(label: str, page: dict[str, Any]) -> str:
    """``"Pages (50 of 120)"`` for a partial page, ``"Pages (12)"`` for a whole list."""
    shown = len(page.get("items", []))
    total = page.get("total", shown)
    return f"{label} ({shown} of {total})" if total > shown else f"{label} ({total})"
