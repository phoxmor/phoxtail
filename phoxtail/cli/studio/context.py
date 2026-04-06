"""``phoxtail studio context`` — render the context briefing for a variant.

Assembles the context document that AI agents use when editing or
creating block variants: block schema, DTL rules, CSS architecture,
design tokens, current variant code, and references.
"""

from __future__ import annotations

from pathlib import Path

import typer
from jinja2 import Environment, FileSystemLoader
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from phoxtail.cli.studio import client

console = Console()

_TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates" / "studio"
_jinja_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATE_DIR)),
    keep_trailing_newline=True,
)


def context(
    block: str = typer.Option(
        ...,
        "--block",
        help="Block identifier.",
    ),
    variant: str = typer.Option(
        ...,
        "--variant",
        help="Variant identifier.",
    ),
    references: str | None = typer.Option(
        None,
        "--references",
        help=(
            "Comma-separated list of variant identifiers to include as "
            "design inspiration."
        ),
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Write the rendered context to a file instead of stdout.",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Emit the raw JSON data instead of the rendered context.",
    ),
    raw: bool = typer.Option(
        False,
        "--raw",
        help="Print plain text without Rich formatting (for piping).",
    ),
) -> None:
    """Render the context briefing for a block variant."""
    ref_list = (
        [r.strip() for r in references.split(",") if r.strip()] if references else []
    )

    # Assemble context from the API and render locally
    data = client.get_context(
        block=block,
        variant=variant,
        references=ref_list,
    )

    if json_output:
        client.emit_json(data)
        return

    jinja_template = _jinja_env.get_template("context.md")
    rendered = jinja_template.render(**data)

    if output is not None:
        output.write_text(rendered)
        console.print(
            f"[green]\u2713[/green] Wrote context to [bold]{output}[/bold] "
            f"([dim]{len(rendered)} chars[/dim])"
        )
        return

    if raw:
        print(rendered)
        return

    # Rich-formatted output
    block_data = data.get("block") or {}
    variant_data = data.get("variant") or {}
    collection_data = data.get("collection") or {}

    console.print(
        Panel(
            f"[bold]{block_data.get('name', '')}[/bold] "
            f"[dim]({block_data.get('identifier', '')})[/dim]  \u2192  "
            f"[bold cyan]{variant_data.get('name', '')}[/bold cyan] "
            f"[dim]({variant_data.get('identifier', '')})[/dim]  \u2014  "
            f"[blue]{collection_data.get('name', '')}[/blue]",
            title="[bold]Studio Context[/bold]",
            border_style="cyan",
            expand=False,
        )
    )
    console.print()
    console.print(Markdown(rendered))
