"""``phoxtail studio discard`` — drop a session without saving."""

from __future__ import annotations

import typer
from rich.console import Console

from phoxtail.cli.studio import session
from phoxtail.cli.studio._session_resolve import resolve_session_id

console = Console()


def discard(
    session_ref: str | None = typer.Option(
        None,
        "--session",
        help="Session ID to discard. Can be omitted when only one session is active.",
    ),
) -> None:
    """Drop a session without saving any changes."""
    session_id = resolve_session_id(session_ref)
    session.discard_session(session_id)
    console.print(f"[yellow]Discarded[/yellow] session [bold]{session_id}[/bold]")
