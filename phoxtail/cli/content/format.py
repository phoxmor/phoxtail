"""Rich formatting helpers for the content CLI."""

from __future__ import annotations

from typing import Any

from rich.console import Console
from rich.table import Table


def render_pages(data: dict[str, Any], console: Console) -> None:
    """Render the output of ``GET /api/content/v1/pages/``."""
    pages = data.get("pages", [])
    total = data.get("total", len(pages))
    if not pages:
        console.print("[dim]No pages found.[/dim]")
        return

    if total > len(pages):
        title = f"Pages ({len(pages)} of {total})"
    else:
        title = f"Pages ({total})"
    table = Table(title=title, expand=True)
    table.add_column("ID", style="dim", no_wrap=True, justify="right")
    table.add_column("Title", style="cyan")
    table.add_column("Slug", style="green", no_wrap=True)
    table.add_column("Type", style="blue")
    table.add_column("Locale", style="yellow", no_wrap=True)
    table.add_column("Live", justify="center")
    table.add_column("URL", overflow="fold")

    for p in pages:
        table.add_row(
            str(p.get("id", "")),
            p.get("title", ""),
            p.get("slug", ""),
            p.get("content_type", ""),
            p.get("locale", ""),
            "✓" if p.get("live") else "✗",
            p.get("url") or "",
        )
    console.print(table)


def render_locales(data: dict[str, Any], console: Console) -> None:
    """Render the output of ``GET /api/content/v1/locales/``."""
    locales = data.get("locales", [])
    if not locales:
        console.print("[dim]No locales found.[/dim]")
        return

    table = Table(title=f"Locales ({len(locales)})", expand=False)
    table.add_column("ID", style="dim", no_wrap=True, justify="right")
    table.add_column("Language Code", style="cyan", no_wrap=True)

    for loc in locales:
        table.add_row(str(loc.get("id", "")), loc.get("language_code", ""))
    console.print(table)


def render_sites(data: dict[str, Any], console: Console) -> None:
    """Render the output of ``GET /api/content/v1/sites/``."""
    sites = data.get("sites", [])
    if not sites:
        console.print("[dim]No sites found.[/dim]")
        return

    table = Table(title=f"Sites ({len(sites)})", expand=True)
    table.add_column("ID", style="dim", no_wrap=True, justify="right")
    table.add_column("Hostname", style="cyan", no_wrap=True)
    table.add_column("Port", justify="right")
    table.add_column("Name", style="green")
    table.add_column("Root Page ID", justify="right")
    table.add_column("Default", justify="center")

    for s in sites:
        table.add_row(
            str(s.get("id", "")),
            s.get("hostname", ""),
            str(s.get("port", "")),
            s.get("site_name", ""),
            str(s.get("root_page_id", "")),
            "✓" if s.get("is_default_site") else "",
        )
    console.print(table)
