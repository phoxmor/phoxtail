"""Django management command passthrough."""

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
def manage(ctx: typer.Context) -> None:
    """Run a Django management command inside the web container.

    Wraps: docker compose run --rm web python manage.py <command> [args]

    Examples:
        phoxtail manage createsuperuser
        phoxtail manage makemigrations
        phoxtail manage migrate
        phoxtail manage shell
        phoxtail manage populate_streams --reset
    """
    if not ctx.args:
        console.print("[red]Error:[/red] No management command specified")
        console.print("[dim]Usage: phoxtail manage <command> [args][/dim]")
        raise typer.Exit(1)

    cmd = [
        "docker",
        "compose",
        "run",
        "--rm",
        "web",
        "python",
        "manage.py",
        *ctx.args,
    ]
    sys.exit(subprocess.call(cmd))
