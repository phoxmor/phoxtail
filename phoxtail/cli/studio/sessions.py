"""``phoxtail studio sessions`` — list active editing sessions."""

from __future__ import annotations

import typer
from rich.console import Console

from phoxtail.cli.studio import client, format, session

console = Console()


def sessions(
    json_output: bool = typer.Option(
        False, "--json", help="Emit raw JSON instead of a Rich table."
    ),
) -> None:
    """List active editing sessions."""
    active = session.list_sessions()
    if json_output:
        client.emit_json({"sessions": active})
    else:
        format.render_sessions(active, console)
