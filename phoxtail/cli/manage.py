"""Django management command passthrough."""

import re
import subprocess
import sys
from typing import Annotated

import questionary
import typer
from rich.console import Console

from phoxtail.cli.utils.docker import docker_env

console = Console()


def _get_django_commands() -> list[tuple[str, str]]:
    """Fetch available Django management commands grouped by app.

    Returns a list of (app_name, command_name) tuples.
    """
    result = subprocess.run(
        [
            "docker",
            "compose",
            "run",
            "--rm",
            "--no-deps",
            "web",
            "python",
            "manage.py",
            "help",
        ],
        capture_output=True,
        text=True,
        env=docker_env(),
    )
    if result.returncode != 0:
        if result.stderr:
            console.print(f"[dim]{result.stderr.strip()}[/dim]")
        return []

    commands: list[tuple[str, str]] = []
    current_app = ""
    for line in result.stdout.splitlines():
        app_match = re.match(r"^\[(.+)]$", line.strip())
        if app_match:
            current_app = app_match.group(1)
        elif current_app and line.startswith("    ") and line.strip():
            commands.append((current_app, line.strip()))
    return commands


def manage(
    ctx: typer.Context,
    command: Annotated[str | None, typer.Argument(help="Django management command to run")] = None,
) -> None:
    """Run a Django management command inside the web container.

    Wraps: docker compose run --rm web python manage.py <command> [args]

    Run without arguments to interactively search and select a command.

    Examples:
        phoxtail manage
        phoxtail manage createsuperuser
        phoxtail manage makemigrations
        phoxtail manage migrate
        phoxtail manage shell
        phoxtail manage populate_streams --reset
    """
    if command is None:
        if not sys.stdin.isatty():
            console.print("[red]Interactive mode requires a terminal.[/red]")
            raise typer.Exit(code=1)

        console.print("Fetching available commands…", style="dim")
        grouped_commands = _get_django_commands()
        if not grouped_commands:
            console.print("[red]Could not fetch commands from the web container.[/red]")
            raise typer.Exit(code=1)

        choices = sorted(
            [f"[{app}] {cmd}" for app, cmd in grouped_commands],
            key=lambda x: x.lower(),
        )
        # Build a set of valid raw command names for fallback matching
        valid_commands = {cmd for _, cmd in grouped_commands}

        selected = questionary.autocomplete(
            "Search commands (by name or app):",
            choices=choices,
            validate=lambda val: val in choices or val in valid_commands,
            style=questionary.Style(
                [
                    ("answer", "fg:green bold"),
                ]
            ),
        ).ask()

        if selected is None:
            raise typer.Exit()
        # Extract the command name — handle both "[app] cmd" format and raw name
        if "] " in selected:
            command = selected.split("] ", 1)[1]
        else:
            command = selected

    cmd = [
        "docker",
        "compose",
        "run",
        "--rm",
        "web",
        "python",
        "manage.py",
        command,
        *ctx.args,
    ]
    sys.exit(subprocess.call(cmd, env=docker_env()))
