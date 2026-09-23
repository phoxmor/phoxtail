"""``phoxtail studio list <kind>`` — list Studio entities."""

from __future__ import annotations

import typer
from rich.console import Console

from phoxtail.cli.studio import client, format
from phoxtail.core.paging import DEFAULT_LIMIT, MAX_LIMIT

app = typer.Typer(help="List Studio entities (variants, collections, blocks).")
console = Console()


@app.command("variants")
def list_variants(
    block: str | None = typer.Option(None, "--block", help="Filter by block identifier."),
    collection: str | None = typer.Option(None, "--collection", help="Filter by collection identifier."),
    search: str | None = typer.Option(None, "--search", "-s", help="Prefix search on variant name and identifier."),
    limit: int = typer.Option(DEFAULT_LIMIT, "--limit", min=1, max=MAX_LIMIT, help="Rows to show."),
    offset: int = typer.Option(0, "--offset", min=0, help="Rows to skip."),
    json_output: bool = typer.Option(False, "--json", help="Emit raw JSON instead of a Rich table."),
) -> None:
    """List BlockVariants a page at a time, optionally filtered by block and/or collection."""
    data = client.list_variants(block=block, collection=collection, search=search, limit=limit, offset=offset)
    if json_output:
        client.emit_json(data)
    else:
        format.render_variants(data, console)


@app.command("collections")
def list_collections(
    search: str | None = typer.Option(None, "--search", "-s", help="Prefix search on collection name and identifier."),
    limit: int = typer.Option(DEFAULT_LIMIT, "--limit", min=1, max=MAX_LIMIT, help="Rows to show."),
    offset: int = typer.Option(0, "--offset", min=0, help="Rows to skip."),
    json_output: bool = typer.Option(False, "--json", help="Emit raw JSON instead of a Rich table."),
) -> None:
    """List VariantCollections, a page at a time."""
    data = client.list_collections(search=search, limit=limit, offset=offset)
    if json_output:
        client.emit_json(data)
    else:
        format.render_collections(data, console)


@app.command("blocks")
def list_blocks(
    search: str | None = typer.Option(None, "--search", "-s", help="Prefix search on block name and identifier."),
    limit: int = typer.Option(DEFAULT_LIMIT, "--limit", min=1, max=MAX_LIMIT, help="Rows to show."),
    offset: int = typer.Option(0, "--offset", min=0, help="Rows to skip."),
    json_output: bool = typer.Option(False, "--json", help="Emit raw JSON instead of a Rich table."),
) -> None:
    """List Blocks, a page at a time."""
    data = client.list_blocks(search=search, limit=limit, offset=offset)
    if json_output:
        client.emit_json(data)
    else:
        format.render_blocks(data, console)
