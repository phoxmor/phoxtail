"""``phoxtail studio list <kind>`` — list Studio entities."""

from __future__ import annotations

import typer
from rich.console import Console

from phoxtail.cli.studio import client, format

app = typer.Typer(help="List Studio entities (variants, collections, blocks, prompts).")
console = Console()


@app.command("variants")
def list_variants(
    block: str | None = typer.Option(
        None, "--block", help="Filter by block identifier."
    ),
    collection: str | None = typer.Option(
        None, "--collection", help="Filter by collection identifier."
    ),
    json_output: bool = typer.Option(
        False, "--json", help="Emit raw JSON instead of a Rich table."
    ),
) -> None:
    """List BlockVariants, optionally filtered by block and/or collection."""
    data = client.list_variants(block=block, collection=collection)
    if json_output:
        client.emit_json(data)
    else:
        format.render_variants(data, console)


@app.command("collections")
def list_collections(
    json_output: bool = typer.Option(
        False, "--json", help="Emit raw JSON instead of a Rich table."
    ),
) -> None:
    """List all VariantCollections."""
    data = client.list_collections()
    if json_output:
        client.emit_json(data)
    else:
        format.render_collections(data, console)


@app.command("blocks")
def list_blocks(
    json_output: bool = typer.Option(
        False, "--json", help="Emit raw JSON instead of a Rich table."
    ),
) -> None:
    """List all Blocks."""
    data = client.list_blocks()
    if json_output:
        client.emit_json(data)
    else:
        format.render_blocks(data, console)


@app.command("prompts")
def list_prompts(
    json_output: bool = typer.Option(
        False, "--json", help="Emit raw JSON instead of a Rich table."
    ),
) -> None:
    """List all BlockSystemPrompts."""
    data = client.list_prompts()
    if json_output:
        client.emit_json(data)
    else:
        format.render_prompts(data, console)
