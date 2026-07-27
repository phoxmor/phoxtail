"""Main CLI entry point for Phoxtail."""

import typer
from rich.console import Console

from phoxtail.cli import (
    auth,
    content,
    db,
    docker,
    env,
    hatch,
    install,
    lint,
    manage,
    mcp,
    media,
    net,
    nginx,
    requirements,
    server,
    ssl,
    studio,
    test,
    upgrade,
)
from phoxtail.cli.utils.config import require_project

app = typer.Typer(
    name="phoxtail",
    help="The engine behind every Phoxtail project.",
    add_completion=True,
    invoke_without_command=True,
)
console = Console()

# Commands that don't require a phoxtail project.
NO_PROJECT_COMMANDS = {"version", "hatch", "server", "mcp", "auth", "net"}


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context):
    """The engine behind every Phoxtail project."""
    if ctx.invoked_subcommand is None:
        console.print(ctx.get_help())
        raise typer.Exit()

    if ctx.invoked_subcommand in NO_PROJECT_COMMANDS or ctx.resilient_parsing:
        return

    require_project()


# Command groups
app.add_typer(docker.app, name="docker", help="Docker lifecycle and configuration")
app.add_typer(db.app, name="db", help="Database operations")
app.add_typer(media.app, name="media", help="Media file management")
app.add_typer(nginx.app, name="nginx", help="Nginx configuration")
app.add_typer(net.app, name="net", help="Shared local network for multiple projects")
app.add_typer(env.app, name="env", help="Environment configuration")
app.add_typer(requirements.app, name="requirements", help="Python requirements")
app.add_typer(server.app, name="server", help="Remote server management")
app.add_typer(ssl.app, name="ssl", help="SSL certificate management")
app.add_typer(mcp.app, name="mcp", help="MCP server for AI agents")
app.add_typer(auth.app, name="auth", help="Manage Phoxtail API credentials")
app.add_typer(studio.app, name="studio", help="Design and exchange block variants")
app.add_typer(content.app, name="content", help="Manage CMS content (pages, locales, sites)")

# Top-level commands
app.command(context_settings={"allow_extra_args": True, "allow_interspersed_args": False})(manage.manage)
app.add_typer(test.app, name="test", help="Run the test suite")
app.add_typer(lint.app, name="lint", help="Run linting and formatting")
app.command()(hatch.hatch)
app.command()(install.install)
app.command()(upgrade.upgrade)


@app.command()
def version():
    """Show the version."""
    from phoxtail import __version__

    console.print(f"Phoxtail v{__version__}", style="bold green")


if __name__ == "__main__":
    app()
