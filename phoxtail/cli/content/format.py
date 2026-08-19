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


def render_images(data: dict[str, Any], console: Console) -> None:
    """Render the output of ``GET /api/content/v1/media/images/``."""
    items = data.get("items", [])
    total = data.get("total", len(items))
    if not items:
        console.print("[dim]No images found.[/dim]")
        return

    n = len(items)
    title = f"Images ({n} of {total})" if total > n else f"Images ({total})"
    table = Table(title=title, expand=True)
    table.add_column("ID", style="dim", no_wrap=True, justify="right")
    table.add_column("Title", style="cyan")
    table.add_column("Dimensions", style="green", no_wrap=True)
    table.add_column("Tags", style="yellow", overflow="fold")
    table.add_column("URL", overflow="fold")

    for img in items:
        w, h = img.get("width") or 0, img.get("height") or 0
        dims = f"{w}×{h}" if w and h else ""
        table.add_row(
            str(img.get("id", "")),
            img.get("title", ""),
            dims,
            _format_tags(img.get("tags", [])),
            img.get("file_url") or "",
        )
    console.print(table)


def render_documents(data: dict[str, Any], console: Console) -> None:
    """Render the output of ``GET /api/content/v1/media/documents/``."""
    items = data.get("items", [])
    total = data.get("total", len(items))
    if not items:
        console.print("[dim]No documents found.[/dim]")
        return

    title = f"Documents ({len(items)} of {total})" if total > len(items) else f"Documents ({total})"
    table = Table(title=title, expand=True)
    table.add_column("ID", style="dim", no_wrap=True, justify="right")
    table.add_column("Title", style="cyan")
    table.add_column("Filename", style="green", overflow="fold")
    table.add_column("Ext", style="blue", no_wrap=True)
    table.add_column("Size", justify="right", no_wrap=True)
    table.add_column("Tags", style="yellow", overflow="fold")

    for doc in items:
        table.add_row(
            str(doc.get("id", "")),
            doc.get("title", ""),
            doc.get("filename", ""),
            doc.get("file_extension", ""),
            _format_size(doc.get("file_size")),
            _format_tags(doc.get("tags", [])),
        )
    console.print(table)


def render_videos(data: dict[str, Any], console: Console) -> None:
    """Render the output of ``GET /api/content/v1/media/videos/``."""
    items = data.get("items", [])
    total = data.get("total", len(items))
    if not items:
        console.print("[dim]No videos found.[/dim]")
        return

    n = len(items)
    title = f"Videos ({n} of {total})" if total > n else f"Videos ({total})"
    table = Table(title=title, expand=True)
    table.add_column("ID", style="dim", no_wrap=True, justify="right")
    table.add_column("Title", style="cyan")
    table.add_column("Duration", style="green", no_wrap=True, justify="right")
    table.add_column("Dimensions", style="blue", no_wrap=True)
    table.add_column("Tags", style="yellow", overflow="fold")

    for vid in items:
        w, h = vid.get("width") or 0, vid.get("height") or 0
        dims = f"{w}×{h}" if w and h else ""
        table.add_row(
            str(vid.get("id", "")),
            vid.get("title", ""),
            _format_duration(vid.get("duration", 0.0)),
            dims,
            _format_tags(vid.get("tags", [])),
        )
    console.print(table)


def render_audio(data: dict[str, Any], console: Console) -> None:
    """Render the output of ``GET /api/content/v1/media/audio/``."""
    items = data.get("items", [])
    total = data.get("total", len(items))
    if not items:
        console.print("[dim]No audio files found.[/dim]")
        return

    title = f"Audio ({len(items)} of {total})" if total > len(items) else f"Audio ({total})"
    table = Table(title=title, expand=True)
    table.add_column("ID", style="dim", no_wrap=True, justify="right")
    table.add_column("Title", style="cyan")
    table.add_column("Duration", style="green", no_wrap=True, justify="right")
    table.add_column("Tags", style="yellow", overflow="fold")

    for aud in items:
        table.add_row(
            str(aud.get("id", "")),
            aud.get("title", ""),
            _format_duration(aud.get("duration", 0.0)),
            _format_tags(aud.get("tags", [])),
        )
    console.print(table)


def _format_tags(tags: list[str]) -> str:
    if not tags:
        return ""
    visible = tags[:3]
    rest = len(tags) - 3
    result = ", ".join(visible)
    return f"{result} +{rest}" if rest > 0 else result


def _format_duration(seconds: float) -> str:
    if not seconds:
        return ""
    total = int(seconds)
    h, remainder = divmod(total, 3600)
    m, s = divmod(remainder, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def _format_size(size: int | None) -> str:
    if size is None:
        return ""
    value = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024:
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} TB"


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
