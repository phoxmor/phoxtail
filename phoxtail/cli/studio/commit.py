"""``phoxtail studio commit`` — write a session back to the database.

Reads the edited files from a session directory and sends them to
``PUT /api/streams/v1/variants/{id}`` with the ``If-Match`` header the
session captured on its initial ``GET``. A 412 from the server means the
variant was modified elsewhere since the session started; the CLI
surfaces the error and preserves the session directory so the user can
resolve the conflict manually.
"""

from __future__ import annotations

import typer
from rich.console import Console

from phoxtail.cli.studio import client, session
from phoxtail.cli.studio._session_resolve import resolve_session_id

console = Console()


def commit(
    session_ref: str | None = typer.Option(
        None,
        "--session",
        help="Session ID to commit. Can be omitted when only one session is active.",
    ),
    message: str | None = typer.Option(
        None,
        "--message",
        "-m",
        help="Optional commit message for the session history.",
    ),
    clean: bool = typer.Option(
        False,
        "--clean",
        help="Remove the session directory after a successful commit.",
    ),
) -> None:
    """Write an active session's files back to the database.

    On success the session directory is kept unless --clean is passed.
    On conflict (412) or any other error the session is always preserved.
    """
    session_id = resolve_session_id(session_ref)
    session_data = session.read_session(session_id)
    variant_meta = session_data["variant"]
    etag = session_data.get("etag") or ""

    if not etag:
        console.print(
            "[red]Error:[/red] session has no stored ETag. This session "
            "was created before optimistic concurrency was wired; "
            "discard it and start a new one."
        )
        raise typer.Exit(code=1)

    updated, new_etag = client.update_variant(
        variant_meta["identifier"],
        html=session_data["html"],
        css=session_data["css"],
        javascript=session_data["javascript"],
        etag=etag,
        block=variant_meta.get("block", {}).get("identifier"),
        collection=variant_meta.get("collection", {}).get("identifier"),
    )

    if clean:
        session.discard_session(session_id)
    elif new_etag:
        session.update_session_etag(session_id, new_etag)

    suffix = f" [dim]({message})[/dim]" if message else ""
    kept = "" if clean else " [dim](session kept)[/dim]"
    console.print(
        f"[green]Committed[/green] session [bold]{session_id}[/bold] "
        f"-> variant [cyan]{updated['identifier']}[/cyan] "
        f"(block: {updated['block']['identifier']}){suffix}{kept}"
    )
