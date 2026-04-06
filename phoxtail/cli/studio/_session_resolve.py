"""Internal helper: resolve which session a CLI verb should operate on.

Shared between ``commit`` and ``discard``. Kept in its own module (with a
leading underscore to mark it as private) because importing verb modules
from each other would tangle the registrar in ``__init__.py``.
"""

from __future__ import annotations

import typer
from rich.console import Console

from phoxtail.cli.studio import session

console = Console()


def resolve_session_id(explicit: str | None) -> str:
    """Resolve which session to operate on.

    If ``explicit`` is given, verify it exists. Otherwise require exactly
    one active session.
    """
    if explicit:
        if not session.session_exists(explicit):
            console.print(f"[red]Error:[/red] Session '{explicit}' not found.")
            raise typer.Exit(code=1)
        return explicit

    active = session.list_sessions()
    if not active:
        console.print("[red]Error:[/red] No active sessions.")
        raise typer.Exit(code=1)
    if len(active) > 1:
        ids = ", ".join(s.get("session_id", "?") for s in active)
        console.print(
            f"[red]Error:[/red] Multiple active sessions ({ids}). "
            "Specify one with --session."
        )
        raise typer.Exit(code=1)
    return active[0]["session_id"]
