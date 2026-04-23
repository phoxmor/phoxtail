"""Phoxtail Studio — CLI sub-app for designing, refining, and exchanging
block variants across Phoxtail projects.

This package is the entry point for every ``phoxtail studio <verb>``
command. Each verb lives in its own module; this file is a thin registrar
that mirrors the structure of ``phoxtail.cli.server``.

See ``phoxtail/docs/docs/studio/`` for the full design and roadmap.
"""

from __future__ import annotations

import typer

app = typer.Typer(help="Design, refine, and exchange block variants.")


def _register_commands() -> None:
    # Nested verb groups
    from phoxtail.cli.studio.list import app as list_app
    from phoxtail.cli.studio.sessions import app as sessions_app
    from phoxtail.cli.studio.show import app as show_app

    app.add_typer(list_app, name="list")
    app.add_typer(show_app, name="show")
    app.add_typer(sessions_app, name="sessions")

    # Flat verbs
    from phoxtail.cli.studio.context import context
    from phoxtail.cli.studio.dump import dump
    from phoxtail.cli.studio.load import load
    from phoxtail.cli.studio.version import version

    app.command("version")(version)
    app.command("context")(context)
    app.command("dump")(dump)
    app.command("load")(load)


_register_commands()
