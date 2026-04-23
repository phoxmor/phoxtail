"""``phoxtail studio show <kind> <id>`` — show a single entity."""

from __future__ import annotations

import typer
from rich.console import Console

from phoxtail.cli.studio import client, format

app = typer.Typer(help="Show a single Studio entity in detail.")
console = Console()


@app.command("variant")
def show_variant(
    variant_id: int = typer.Argument(..., help="Variant ID."),
    json_output: bool = typer.Option(
        False, "--json", help="Emit raw JSON instead of a Rich detail view."
    ),
) -> None:
    """Show a BlockVariant in detail, including HTML, CSS, and JavaScript."""
    data, _etag = client.get_variant_by_id(variant_id)
    if json_output:
        client.emit_json(data)
    else:
        format.render_variant_detail(data, console)


@app.command("collection")
def show_collection(
    collection_id: int = typer.Argument(..., help="Collection ID."),
    json_output: bool = typer.Option(
        False, "--json", help="Emit raw JSON instead of a Rich detail view."
    ),
) -> None:
    """Show a VariantCollection in detail."""
    data, _etag = client.get_collection_by_id(collection_id)
    if json_output:
        client.emit_json(data)
    else:
        format.render_collection_detail(data, console)


@app.command("block")
def show_block(
    block_id: int = typer.Argument(..., help="Block ID."),
    json_output: bool = typer.Option(
        False, "--json", help="Emit raw JSON instead of a Rich detail view."
    ),
) -> None:
    """Show a Block in detail, including its variants and page types."""
    data, _etag = client.get_block_by_id(block_id)
    if json_output:
        client.emit_json(data)
    else:
        format.render_block_detail(data, console)
