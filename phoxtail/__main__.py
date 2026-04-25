"""Main CLI entry point for Phoxtail."""

import typer
from rich.console import Console
from rich.panel import Panel

from phoxtail.cli import (
    auth,
    content,
    db,
    docker,
    docs,
    env,
    hatch,
    lint,
    manage,
    mcp,
    media,
    nginx,
    requirements,
    server,
    ssl,
    studio,
    test,
)
from phoxtail.cli.utils.config import find_config_file

app = typer.Typer(
    name="phoxtail",
    help="The engine behind every Phoxtail project.",
    add_completion=True,
    invoke_without_command=True,
)
console = Console()

# Commands that don't require a phoxtail project.
NO_PROJECT_COMMANDS = {"version", "hatch", "docs", "server", "mcp", "auth"}


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context):
    """The engine behind every Phoxtail project."""
    if ctx.invoked_subcommand is None:
        console.print(ctx.get_help())
        raise typer.Exit()

    if ctx.invoked_subcommand in NO_PROJECT_COMMANDS or ctx.resilient_parsing:
        return

    if find_config_file() is None:
        console.print(
            Panel(
                "No [bold]phoxtail.toml[/bold] found in this directory or any parent.\n"
                "Run this command from the root of a Phoxtail project.",
                title="[red]Not a Phoxtail project[/red]",
                border_style="red",
                expand=False,
            )
        )
        raise typer.Exit(code=1)


# Command groups
app.add_typer(docker.app, name="docker", help="Docker lifecycle and configuration")
app.add_typer(db.app, name="db", help="Database operations")
app.add_typer(media.app, name="media", help="Media file management")
app.add_typer(nginx.app, name="nginx", help="Nginx configuration")
app.add_typer(env.app, name="env", help="Environment configuration")
app.add_typer(requirements.app, name="requirements", help="Python requirements")
app.add_typer(server.app, name="server", help="Remote server management")
app.add_typer(ssl.app, name="ssl", help="SSL certificate management")
app.add_typer(mcp.app, name="mcp", help="MCP server for AI agents")
app.add_typer(auth.app, name="auth", help="Manage Phoxtail API credentials")
app.add_typer(studio.app, name="studio", help="Design and exchange block variants")
app.add_typer(
    content.app, name="content", help="Manage CMS content (pages, locales, sites)"
)

# Top-level commands
app.command(
    context_settings={"allow_extra_args": True, "allow_interspersed_args": False}
)(manage.manage)
app.add_typer(test.app, name="test", help="Run the test suite")
app.add_typer(lint.app, name="lint", help="Run linting and formatting")
app.command()(hatch.hatch)
app.add_typer(docs.app, name="docs", help="Serve the Phoxtail documentation")


@app.command()
def version():
    """Show the version."""
    from phoxtail import __version__

    console.print(f"Phoxtail v{__version__}", style="bold green")


if __name__ == "__main__":
    app()
