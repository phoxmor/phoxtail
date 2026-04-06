"""``phoxtail studio edit <variant>`` — start an editing session.

Fetches the variant and a rendered system prompt from the API, then
writes them to disk as a working copy under ``.phoxtail/studio/<id>/``.
The ETag captured on the initial ``GET /variants/{id}`` is stored in
``session.json`` so ``commit`` can send it back as ``If-Match`` for
optimistic concurrency.
"""

from __future__ import annotations

import typer
from rich.console import Console

from phoxtail.cli.studio import client, session

console = Console()


def edit(
    variant_identifier: str = typer.Argument(..., help="Variant identifier to edit."),
    template: str | None = typer.Option(
        None,
        "--template",
        help=(
            "BlockSystemPrompt identifier for context.md. Defaults to "
            "'variant_editor' if it exists, else 'variant_refiner'."
        ),
    ),
    block: str = typer.Option(..., "--block", help="Block identifier."),
    collection: str | None = typer.Option(
        None, "--collection", help="Disambiguate by collection identifier."
    ),
) -> None:
    """Start an editing session on a variant.

    Creates a working copy under ``.phoxtail/studio/<session-id>/`` with
    the variant's HTML, CSS, and JavaScript as editable files, plus a
    rendered system prompt as ``context.md``.
    """
    # 1. Fetch the variant (captures ETag for later If-Match).
    variant_data, etag = client.get_variant(
        variant_identifier, block=block, collection=collection
    )

    # 2. Resolve the template with the variant_editor → variant_refiner
    #    cascade when the user did not pick one explicitly.
    resolved_template = _resolve_template(template)
    context_md = ""
    template_used = ""
    if resolved_template:
        payload = client.render_prompt(
            resolved_template,
            variant=variant_data["identifier"],
            block=variant_data["block"]["identifier"],
            collection=variant_data["collection"]["identifier"],
        )
        context_md = payload.get("prompt", "")
        template_used = resolved_template

    # 3. Write the session to disk.
    session_id = session.derive_session_id(variant_data["identifier"])
    sdir = session.create_session(
        session_id=session_id,
        variant_data=variant_data,
        context_md=context_md,
        template_used=template_used,
        etag=etag or "",
    )

    console.print(
        f"[green]Session started:[/green] [bold]{session_id}[/bold]\n"
        f"  [dim]Path:[/dim]    {sdir}\n"
        f"  [dim]Variant:[/dim] {variant_data['identifier']} "
        f"({variant_data['block']['identifier']})\n"
        f"  [dim]Files:[/dim]   template.html, style.css, script.js, "
        f"context.md"
    )


def _resolve_template(explicit: str | None) -> str | None:
    """Pick a prompt template identifier.

    If the user passed ``--template``, use it verbatim (let the render
    call surface any "not found" error). Otherwise try ``variant_editor``
    then ``variant_refiner``; if neither exists, return ``None`` and the
    session is created without a ``context.md``.
    """
    if explicit:
        return explicit
    for candidate in ("variant_editor", "variant_refiner"):
        if client.prompt_exists(candidate):
            return candidate
    return None
