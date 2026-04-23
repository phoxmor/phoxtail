"""``phoxtail studio refresh`` — re-fetch the ETag for a session.

Useful when a session's stored ETag is stale (e.g. the variant was
committed from another session or edited directly in the admin).
Local file edits are untouched; only ``session.json`` is updated.
"""

from __future__ import annotations

import typer
from rich.console import Console

from phoxtail.cli.studio import client, session
from phoxtail.cli.studio._session_resolve import resolve_session_id

console = Console()


def refresh(
    session_ref: str | None = typer.Option(
        None,
        "--session",
        help="Session ID to refresh. Can be omitted when only one session is active.",
    ),
) -> None:
    """Re-fetch the server ETag for a session without touching local files."""
    session_id = resolve_session_id(session_ref)
    session_data = session.read_session(session_id)
    variant_meta = session_data["variant"]

    _, new_etag = client.get_variant(
        variant_meta["identifier"],
        block=variant_meta.get("block", {}).get("identifier"),
        collection=variant_meta.get("collection", {}).get("identifier"),
    )

    if not new_etag:
        console.print("[red]Error:[/red] server returned no ETag for this variant.")
        raise typer.Exit(code=1)

    session.update_session_etag(session_id, new_etag)
    console.print(
        f"[green]Refreshed[/green] session [bold]{session_id}[/bold] "
        f"ETag -> [dim]{new_etag}[/dim]"
    )
