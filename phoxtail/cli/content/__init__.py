"""``phoxtail content`` — CMS content management commands."""

from __future__ import annotations

import typer

app = typer.Typer(help="Manage CMS content (pages, locales, sites).")


def _register_commands() -> None:
    from phoxtail.cli.content.list import app as list_app

    app.add_typer(list_app, name="list")


_register_commands()
