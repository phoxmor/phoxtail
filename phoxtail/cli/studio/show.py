"""``phoxtail studio show <kind> <identifier>`` — show a single entity."""

from __future__ import annotations

import typer
from rich.console import Console

from phoxtail.cli.studio import client, format

app = typer.Typer(help="Show a single Studio entity in detail.")
console = Console()


@app.command("variant")
def show_variant(
    identifier: str = typer.Argument(..., help="Variant identifier."),
    block: str = typer.Option(..., "--block", help="Block identifier."),
    collection: str | None = typer.Option(
        None, "--collection", help="Disambiguate by collection identifier."
    ),
    json_output: bool = typer.Option(
        False, "--json", help="Emit raw JSON instead of a Rich detail view."
    ),
) -> None:
    """Show a BlockVariant in detail, including HTML, CSS, and JavaScript."""
    data, _etag = client.get_variant(identifier, block=block, collection=collection)
    if json_output:
        client.emit_json(data)
    else:
        format.render_variant_detail(data, console)


@app.command("collection")
def show_collection(
    identifier: str = typer.Argument(..., help="Collection identifier."),
    json_output: bool = typer.Option(
        False, "--json", help="Emit raw JSON instead of a Rich detail view."
    ),
) -> None:
    """Show a VariantCollection in detail."""
    data = client.get_collection(identifier)
    if json_output:
        client.emit_json(data)
    else:
        format.render_collection_detail(data, console)


@app.command("block")
def show_block(
    identifier: str = typer.Argument(..., help="Block identifier."),
    json_output: bool = typer.Option(
        False, "--json", help="Emit raw JSON instead of a Rich detail view."
    ),
) -> None:
    """Show a Block in detail, including its variants and page types."""
    data = client.get_block(identifier)
    if json_output:
        client.emit_json(data)
    else:
        format.render_block_detail(data, console)
