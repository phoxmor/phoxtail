"""``phoxtail content list`` — list CMS entities."""

from __future__ import annotations

import typer
from rich.console import Console

from phoxtail.cli.content import client, format

app = typer.Typer(help="List CMS entities (pages, locales, sites, images, documents, videos, audio).")
console = Console()


@app.command("pages")
def list_pages(
    search: str | None = typer.Option(None, "--search", "-s", help="Autocomplete prefix search on page title."),
    type: str | None = typer.Option(None, "--type", help="Filter by content type, e.g. 'myapp.BlogPostPage'."),
    parent: int | None = typer.Option(None, "--parent", help="Filter by parent page ID."),
    live: bool | None = typer.Option(None, "--live/--no-live", help="Filter by live status."),
    locale: str | None = typer.Option(None, "--locale", help="Filter by locale language code, e.g. 'en'."),
    site: int | None = typer.Option(None, "--site", help="Filter by site ID."),
    limit: int = typer.Option(50, "--limit", help="Maximum results to return."),
    json_output: bool = typer.Option(False, "--json", help="Emit raw JSON instead of a Rich table."),
) -> None:
    """List pages; filter by type, parent, live, locale, site, or search."""
    data = client.list_pages(
        search=search,
        type=type,
        parent=parent,
        live=live,
        locale=locale,
        site=site,
        limit=limit,
    )
    if json_output:
        client.emit_json(data)
    else:
        format.render_pages(data, console)


@app.command("images")
def list_images(
    search: str | None = typer.Option(None, "--search", "-s", help="Substring match on title."),
    limit: int = typer.Option(50, "--limit", help="Maximum results to return."),
    json_output: bool = typer.Option(False, "--json", help="Emit raw JSON instead of a Rich table."),
) -> None:
    """List images in the Wagtail media library."""
    data = client.list_images(search=search, limit=limit)
    if json_output:
        client.emit_json(data)
    else:
        format.render_images(data, console)


@app.command("documents")
def list_documents(
    search: str | None = typer.Option(None, "--search", "-s", help="Substring match on title."),
    limit: int = typer.Option(50, "--limit", help="Maximum results to return."),
    json_output: bool = typer.Option(False, "--json", help="Emit raw JSON instead of a Rich table."),
) -> None:
    """List documents in the Wagtail library."""
    data = client.list_documents(search=search, limit=limit)
    if json_output:
        client.emit_json(data)
    else:
        format.render_documents(data, console)


@app.command("videos")
def list_videos(
    search: str | None = typer.Option(None, "--search", "-s", help="Substring match on title."),
    limit: int = typer.Option(50, "--limit", help="Maximum results to return."),
    json_output: bool = typer.Option(False, "--json", help="Emit raw JSON instead of a Rich table."),
) -> None:
    """List videos in the Wagtail media library."""
    data = client.list_videos(search=search, limit=limit)
    if json_output:
        client.emit_json(data)
    else:
        format.render_videos(data, console)


@app.command("audio")
def list_audio(
    search: str | None = typer.Option(None, "--search", "-s", help="Substring match on title."),
    limit: int = typer.Option(50, "--limit", help="Maximum results to return."),
    json_output: bool = typer.Option(False, "--json", help="Emit raw JSON instead of a Rich table."),
) -> None:
    """List audio files in the Wagtail media library."""
    data = client.list_audio(search=search, limit=limit)
    if json_output:
        client.emit_json(data)
    else:
        format.render_audio(data, console)


@app.command("locales")
def list_locales(
    json_output: bool = typer.Option(False, "--json", help="Emit raw JSON instead of a Rich table."),
) -> None:
    """List all Wagtail locales."""
    data = client.list_locales()
    if json_output:
        client.emit_json(data)
    else:
        format.render_locales(data, console)


@app.command("sites")
def list_sites(
    json_output: bool = typer.Option(False, "--json", help="Emit raw JSON instead of a Rich table."),
) -> None:
    """List all Wagtail sites."""
    data = client.list_sites()
    if json_output:
        client.emit_json(data)
    else:
        format.render_sites(data, console)
