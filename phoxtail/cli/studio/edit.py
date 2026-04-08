"""``phoxtail studio edit <variant>`` — start an editing session.

Fetches the variant and assembles a context briefing from the API, then
writes them to disk as a working copy under ``.phoxtail/studio/<id>/``.
The ETag captured on the initial ``GET /variants/{id}`` is stored in
``session.json`` so ``commit`` can send it back as ``If-Match`` for
optimistic concurrency.
"""

from __future__ import annotations

from pathlib import Path

import typer
from jinja2 import Environment, FileSystemLoader
from rich.console import Console

from phoxtail.cli.studio import client, session

console = Console()

_TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates" / "studio"
_jinja_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATE_DIR)),
    keep_trailing_newline=True,
)


def edit(
    variant_identifier: str = typer.Argument(..., help="Variant identifier to edit."),
    block: str = typer.Option(..., "--block", help="Block identifier."),
    collection: str | None = typer.Option(
        None, "--collection", help="Disambiguate by collection identifier."
    ),
) -> None:
    """Start an editing session on a variant.

    Creates a working copy under ``.phoxtail/studio/<session-id>/`` with
    the variant's HTML, CSS, and JavaScript as editable files, plus a
    rendered context briefing as ``context.md``.
    """
    # 1. Fetch the variant (captures ETag for later If-Match).
    variant_data, etag = client.get_variant(
        variant_identifier, block=block, collection=collection
    )

    # 2. Assemble context from the API and render the context template.
    context_md = ""
    try:
        data = client.get_context(
            block=variant_data["block"]["identifier"],
            variant=variant_data["identifier"],
        )
        jinja_template = _jinja_env.get_template("variant_design_context.md")
        context_md = jinja_template.render(**data)
    except Exception:
        # Non-fatal: the session is still usable without context.
        pass

    # 3. Write the session to disk.
    session_id = session.derive_session_id(variant_data["identifier"])
    sdir = session.create_session(
        session_id=session_id,
        variant_data=variant_data,
        context_md=context_md,
        template_used="context",
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
