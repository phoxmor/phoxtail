"""Manage remote servers for Phoxtail projects."""

import typer

app = typer.Typer(help="Manage remote servers for Phoxtail projects.")


def _register_commands() -> None:
    from phoxtail.cli.server.deploy import deploy
    from phoxtail.cli.server.provision import provision
    from phoxtail.cli.server.ssl import ssl

    app.command("provision")(provision)
    app.command("deploy")(deploy)
    app.command("ssl")(ssl)


_register_commands()
