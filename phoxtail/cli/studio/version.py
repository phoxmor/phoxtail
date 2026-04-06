"""``phoxtail studio version`` — print the Studio sub-app version."""

from __future__ import annotations

from rich.console import Console

console = Console()


def version() -> None:
    """Show the Studio sub-app version."""
    from phoxtail import __version__

    console.print(f"Phoxtail Studio v{__version__}", style="bold green")
