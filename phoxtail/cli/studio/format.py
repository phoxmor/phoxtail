"""Shared Rich formatting helpers for the Phoxtail Studio CLI.

Every function here takes a JSON-serializable dict shaped by the streams
v1 API and renders it with Rich. The rendering functions only know how
to display shapes — they never speak HTTP or touch the database.
"""

from __future__ import annotations

from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text

# ---------------------------------------------------------------------------
# List renderers
# ---------------------------------------------------------------------------


def render_variants(data: dict[str, Any], console: Console) -> None:
    """Render the output of ``GET /variants``."""
    variants = data.get("variants", [])
    if not variants:
        console.print("[dim]No variants found.[/dim]")
        return

    table = Table(title=f"Variants ({len(variants)})", expand=True)
    table.add_column("ID", style="dim", no_wrap=True, justify="right")
    table.add_column("Identifier", style="cyan", no_wrap=True)
    table.add_column("Name")
    table.add_column("Block", style="magenta")
    table.add_column("Collection", style="blue")
    table.add_column("Default", justify="center")

    for v in variants:
        block = v.get("block") or {}
        collection = v.get("collection") or {}
        table.add_row(
            str(v.get("id", "")),
            v.get("identifier", ""),
            v.get("name", ""),
            block.get("identifier", ""),
            collection.get("identifier", ""),
            "✓" if v.get("is_default") else "",
        )
    console.print(table)


def render_collections(data: dict[str, Any], console: Console) -> None:
    """Render the output of ``GET /collections``."""
    collections = data.get("collections", [])
    if not collections:
        console.print("[dim]No collections found.[/dim]")
        return

    table = Table(title=f"Collections ({len(collections)})", expand=True)
    table.add_column("ID", style="dim", no_wrap=True, justify="right")
    table.add_column("Identifier", style="cyan", no_wrap=True)
    table.add_column("Name")
    table.add_column("Variants", justify="right")
    table.add_column("Description", overflow="fold")

    for c in collections:
        table.add_row(
            str(c.get("id", "")),
            c.get("identifier", ""),
            c.get("name", ""),
            str(c.get("variant_count", 0)),
            c.get("description", ""),
        )
    console.print(table)


def render_blocks(data: dict[str, Any], console: Console) -> None:
    """Render the output of ``GET /blocks``."""
    blocks = data.get("blocks", [])
    if not blocks:
        console.print("[dim]No blocks found.[/dim]")
        return

    table = Table(title=f"Blocks ({len(blocks)})", expand=True)
    table.add_column("ID", style="dim", no_wrap=True, justify="right")
    table.add_column("Identifier", style="cyan", no_wrap=True)
    table.add_column("Name")
    table.add_column("Group", style="blue")
    table.add_column("Shared", justify="center")
    table.add_column("Variants", justify="right")
    table.add_column("Description", overflow="fold")

    for b in blocks:
        table.add_row(
            str(b.get("id", "")),
            b.get("identifier", ""),
            b.get("name", ""),
            b.get("group", ""),
            "✓" if b.get("is_shared") else "",
            str(b.get("variant_count", 0)),
            b.get("description", ""),
        )
    console.print(table)


# ---------------------------------------------------------------------------
# Detail renderers
# ---------------------------------------------------------------------------


def _kv_text(rows: list[tuple[str, str]]) -> Text:
    text = Text()
    for i, (label, value) in enumerate(rows):
        if i > 0:
            text.append("\n")
        text.append(f"{label}: ", style="bold")
        text.append(value or "")
    return text


def render_variant_detail(variant: dict[str, Any], console: Console) -> None:
    """Render a single variant response body (``GET /variants/{id}``)."""
    block = variant.get("block") or {}
    collection = variant.get("collection") or {}

    header_rows = [
        ("Identifier", variant.get("identifier", "")),
        ("Name", variant.get("name", "")),
        ("Block", f"{block.get('identifier', '')} ({block.get('name', '')})"),
        (
            "Collection",
            f"{collection.get('identifier', '')} ({collection.get('name', '')})",
        ),
        ("Default", "yes" if variant.get("is_default") else "no"),
    ]
    console.print(
        Panel(
            _kv_text(header_rows),
            title=f"[bold]Variant[/bold] — {variant.get('name', '')}",
            border_style="cyan",
            expand=False,
        )
    )
    if variant.get("description"):
        console.print(
            Panel(
                variant["description"],
                title="Description",
                border_style="dim",
                expand=False,
            )
        )
    if variant.get("html"):
        console.print(
            Panel(
                Syntax(variant["html"], "html", line_numbers=True, word_wrap=True),
                title="HTML",
                border_style="green",
            )
        )
    if variant.get("css"):
        console.print(
            Panel(
                Syntax(variant["css"], "css", line_numbers=True, word_wrap=True),
                title="CSS",
                border_style="yellow",
            )
        )
    if variant.get("javascript"):
        console.print(
            Panel(
                Syntax(
                    variant["javascript"],
                    "javascript",
                    line_numbers=True,
                    word_wrap=True,
                ),
                title="JavaScript",
                border_style="magenta",
            )
        )


def render_collection_detail(collection: dict[str, Any], console: Console) -> None:
    """Render a single collection response body (``GET /collections/{id}``)."""
    header_rows = [
        ("Identifier", collection.get("identifier", "")),
        ("Name", collection.get("name", "")),
        ("Variants", str(collection.get("variant_count", 0))),
    ]
    console.print(
        Panel(
            _kv_text(header_rows),
            title=f"[bold]Collection[/bold] — {collection.get('name', '')}",
            border_style="blue",
            expand=False,
        )
    )
    if collection.get("description"):
        console.print(
            Panel(
                collection["description"],
                title="Description",
                border_style="dim",
                expand=False,
            )
        )
    if collection.get("template"):
        console.print(
            Panel(
                Syntax(
                    collection["template"],
                    "django",
                    line_numbers=True,
                    word_wrap=True,
                ),
                title="Template (DTL)",
                border_style="yellow",
            )
        )


def render_block_detail(block: dict[str, Any], console: Console) -> None:
    """Render a single block response body (``GET /blocks/{id}``)."""
    header_rows = [
        ("Identifier", block.get("identifier", "")),
        ("Name", block.get("name", "")),
        ("Group", block.get("group", "") or "(none)"),
        ("Icon", block.get("icon", "") or "(none)"),
        ("Shared", "yes" if block.get("is_shared") else "no"),
        ("Variants", str(block.get("variant_count", 0))),
    ]
    console.print(
        Panel(
            _kv_text(header_rows),
            title=f"[bold]Block[/bold] — {block.get('name', '')}",
            border_style="magenta",
            expand=False,
        )
    )
    if block.get("description"):
        console.print(
            Panel(
                block["description"],
                title="Description",
                border_style="dim",
                expand=False,
            )
        )

    page_types = block.get("page_types") or []
    if page_types:
        console.print(
            Panel(
                "\n".join(f"• {pt}" for pt in page_types),
                title="Page Types",
                border_style="blue",
                expand=False,
            )
        )

    variants = block.get("variants") or []
    if variants:
        table = Table(title="Variants", expand=True)
        table.add_column("Identifier", style="cyan", no_wrap=True)
        table.add_column("Name")
        table.add_column("Collection", style="blue")
        table.add_column("Default", justify="center")
        for v in variants:
            collection = v.get("collection") or {}
            table.add_row(
                v.get("identifier", ""),
                v.get("name", ""),
                collection.get("identifier", ""),
                "✓" if v.get("is_default") else "",
            )
        console.print(table)


def render_sessions(sessions: list[dict[str, Any]], console: Console) -> None:
    """Render a list of active editing sessions."""
    if not sessions:
        console.print("[dim]No active sessions.[/dim]")
        return

    table = Table(title=f"Active Sessions ({len(sessions)})", expand=True)
    table.add_column("Session ID", style="cyan", no_wrap=True)
    table.add_column("Variant")
    table.add_column("Block", style="magenta")
    table.add_column("Collection", style="blue")
    table.add_column("Started", style="dim")
    table.add_column("Template", style="dim")

    for s in sessions:
        variant = s.get("variant") or {}
        block = variant.get("block") or {}
        collection = variant.get("collection") or {}
        started = s.get("started_at", "")
        if started:
            # Show just date and time, no microseconds
            started = started[:19].replace("T", " ")
        table.add_row(
            s.get("session_id", ""),
            variant.get("identifier", ""),
            block.get("identifier", ""),
            collection.get("identifier", ""),
            started,
            s.get("template", ""),
        )
    console.print(table)
