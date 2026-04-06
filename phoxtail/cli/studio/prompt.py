"""``phoxtail studio prompt`` — render a system prompt for a variant.

Direct replacement for the Wagtail-admin Studio's "copy prompt to
clipboard" workflow. Calls ``POST /api/streams/v1/prompts/{id}/render``
which reuses ``BlockSystemPrompt.render()`` unchanged, so the output is
byte-identical to the admin UI's equivalent.
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from phoxtail.cli.studio import client

console = Console()


def render_prompt(
    variant: str = typer.Option(
        ..., "--variant", help="Variant identifier to render the prompt for."
    ),
    template: str = typer.Option(
        ...,
        "--template",
        help="BlockSystemPrompt identifier (e.g. 'variant_refiner').",
    ),
    collection: str | None = typer.Option(
        None,
        "--collection",
        help=(
            "Collection identifier override. Defaults to the variant's own collection."
        ),
    ),
    references: str | None = typer.Option(
        None,
        "--references",
        help=(
            "Comma-separated list of variant identifiers to include as "
            "design inspiration."
        ),
    ),
    block: str = typer.Option(
        ...,
        "--block",
        help="Block identifier for the variant.",
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Write the rendered prompt to a file instead of stdout.",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help=(
            "Emit the full JSON payload (rendered prompt + resolution "
            "metadata) instead of the raw prompt text."
        ),
    ),
) -> None:
    """Render a system prompt for a variant via the Studio prompt pipeline."""
    ref_list = (
        [r.strip() for r in references.split(",") if r.strip()] if references else []
    )
    data = client.render_prompt(
        template,
        variant=variant,
        block=block,
        collection=collection,
        references=ref_list,
    )

    if json_output:
        client.emit_json(data)
        return

    prompt_text = data.get("prompt", "")
    if output is not None:
        output.write_text(prompt_text)
        console.print(
            f"[green]✓[/green] Wrote rendered prompt to [bold]{output}[/bold] "
            f"([dim]{len(prompt_text)} chars[/dim])"
        )
        return

    # Print the raw prompt text with no Rich markup / no highlighting so it
    # can be piped cleanly (pbcopy, xclip, claude, etc).
    print(prompt_text)
