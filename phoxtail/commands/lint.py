"""Linting commands."""

import subprocess
import sys

import typer
from rich.console import Console

app = typer.Typer(
    add_completion=False,
    invoke_without_command=True,
    context_settings={"allow_extra_args": True, "allow_interspersed_args": False},
)
console = Console()


@app.callback()
def lint(
    ctx: typer.Context,
    fix: bool = typer.Option(True, "--fix/--no-fix", help="Auto-fix issues"),
    templates: bool = typer.Option(
        True, "--templates/--no-templates", help="Include djlint template formatting"
    ),
) -> None:
    """Run code linting and formatting.

    Runs ruff (import sorting, unused import removal, formatting) and
    djlint (template formatting) inside the Docker web container.

    Examples:
        phoxtail lint
        phoxtail lint --no-fix
        phoxtail lint --no-templates
    """
    ruff_cmd = "ruff check --select I,F401"
    if fix:
        ruff_cmd += " --fix"
    ruff_cmd += " && ruff format"

    if templates:
        ruff_cmd += " && djlint . --reformat"

    cmd = [
        "docker",
        "compose",
        "run",
        "--rm",
        "web",
        "sh",
        "-c",
        ruff_cmd,
    ]
    sys.exit(subprocess.call(cmd))
