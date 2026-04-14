"""Docker-related commands: lifecycle and file generation."""

import subprocess
import sys
from pathlib import Path

import questionary
import typer
from rich.console import Console
from rich.prompt import Confirm, Prompt

from phoxtail.cli.utils.config import any_app_requires_celery, get_project_name
from phoxtail.cli.utils.docker import docker_env
from phoxtail.cli.utils.templates import render_template

app = typer.Typer()
create_app = typer.Typer()
app.add_typer(create_app, name="create", help="Create Docker-related files")
console = Console()


@app.command(
    context_settings={
        "allow_extra_args": True,
        "allow_interspersed_args": False,
        "ignore_unknown_options": True,
    }
)
def up(
    ctx: typer.Context,
    detach: bool = typer.Option(
        True, "--detach/--no-detach", "-d", help="Run in background"
    ),
    build: bool = typer.Option(
        False, "--build", "-b", help="Build images before starting"
    ),
) -> None:
    """Start Docker services.

    Extra arguments are passed through to docker compose up.

    Examples:
        phoxtail docker up
        phoxtail docker up --no-detach
        phoxtail docker up --build
        phoxtail docker up --scale web=2
    """
    cmd = ["docker", "compose", "up"]
    if detach:
        cmd.append("-d")
    if build:
        cmd.append("--build")
    cmd.extend(ctx.args)
    sys.exit(subprocess.call(cmd, env=docker_env()))


@app.command(
    context_settings={
        "allow_extra_args": True,
        "allow_interspersed_args": False,
        "ignore_unknown_options": True,
    }
)
def down(ctx: typer.Context) -> None:
    """Stop Docker services.

    Extra arguments are passed through to docker compose down.

    Examples:
        phoxtail docker down
        phoxtail docker down --volumes
    """
    cmd = ["docker", "compose", "down", *ctx.args]
    sys.exit(subprocess.call(cmd, env=docker_env()))


@app.command(
    context_settings={
        "allow_extra_args": True,
        "allow_interspersed_args": False,
        "ignore_unknown_options": True,
    }
)
def restart(ctx: typer.Context) -> None:
    """Restart Docker services.

    Extra arguments are passed through to docker compose restart.

    Examples:
        phoxtail docker restart
        phoxtail docker restart web
    """
    cmd = ["docker", "compose", "restart", *ctx.args]
    sys.exit(subprocess.call(cmd, env=docker_env()))


# Valid versions for selection
PYTHON_VERSIONS = ["3.11", "3.12", "3.13"]
POSTGRES_VERSIONS = ["15", "16", "17", "18"]

IMAGE_PREFIX = get_project_name()


def _get_postgres_data_path(version: str) -> str:
    """Get the PostgreSQL data directory path for a given version.

    PostgreSQL 18+ uses /var/lib/postgresql (version-specific subdirs).
    PostgreSQL 17 and below use /var/lib/postgresql/data.
    """
    return "/var/lib/postgresql" if int(version) >= 18 else "/var/lib/postgresql/data"


def _get_phoxtail_source() -> str:
    """Get the absolute path to the local phoxtail package directory.

    Used to mount the local (unpublished) library apps into Docker
    containers during development.
    """
    import phoxtail

    return str(Path(phoxtail.__file__).resolve().parent)


@create_app.command("dockerfile")
def dockerfile(
    python_version: str | None = typer.Option(
        None,
        "--python-version",
        "-p",
        help="Python version (3.11, 3.12, 3.13)",
    ),
    port: int = typer.Option(
        80,
        "--port",
        help="Port to expose and run the application on",
    ),
    gunicorn_workers: int = typer.Option(
        3,
        "--workers",
        "-w",
        help="Number of Gunicorn worker processes for production",
    ),
    output: Path = typer.Option(
        Path("Dockerfile"),
        "--output",
        "-o",
        help="Output file path",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Overwrite existing file without prompting",
    ),
) -> None:
    """Create a Dockerfile for Django/Wagtail projects.

    Generates a multi-stage Dockerfile with:
    - Base stage: Python dependencies and system packages
    - Development stage: Django runserver
    - Production stage: Gunicorn WSGI server

    Examples:
        phoxtail docker create dockerfile
        phoxtail docker create dockerfile --python-version 3.12
        phoxtail docker create dockerfile --port 8000 --workers 4
    """
    if output.exists() and not force:
        if not Confirm.ask(
            f"[yellow]Warning:[/yellow] {output} already exists. Overwrite?",
            default=False,
        ):
            console.print("[dim]Cancelled.[/dim]")
            raise typer.Exit(0)

    if python_version is None:
        python_version = questionary.select(
            "Select Python version:",
            choices=PYTHON_VERSIONS,
            default="3.12",
        ).ask()

        if python_version is None:
            console.print("\n[dim]Cancelled.[/dim]")
            raise typer.Exit(0)
    elif python_version not in PYTHON_VERSIONS:
        console.print(
            f"[red]Error:[/red] Invalid Python version '{python_version}'. "
            f"Must be one of: {', '.join(PYTHON_VERSIONS)}"
        )
        raise typer.Exit(1)

    if port < 1 or port > 65535:
        console.print(
            f"[red]Error:[/red] Invalid port '{port}'. Must be between 1 and 65535"
        )
        raise typer.Exit(1)

    if gunicorn_workers < 1:
        console.print(
            f"[red]Error:[/red] Invalid worker count '{gunicorn_workers}'. "
            "Must be at least 1"
        )
        raise typer.Exit(1)

    try:
        content = render_template(
            "docker/Dockerfile",
            {
                "python_version": python_version,
                "port": port,
                "gunicorn_workers": gunicorn_workers,
            },
        )
        output.write_text(content)
        console.print(f"[green]✓[/green] Dockerfile created: [bold]{output}[/bold]")
        console.print(f"[dim]Python version:[/dim] {python_version}")
        console.print(f"[dim]Port:[/dim] {port}")
        console.print(f"[dim]Gunicorn workers:[/dim] {gunicorn_workers}")
    except KeyboardInterrupt:
        console.print("\n[dim]Cancelled.[/dim]")
        raise typer.Exit(0)
    except Exception as e:
        console.print(f"[red]Error creating Dockerfile:[/red] {e}")
        raise typer.Exit(1)


@create_app.command("compose")
def compose(
    environment: str | None = typer.Argument(
        None,
        help="Environment type: 'development' or 'production'",
    ),
    project_name: str | None = typer.Option(
        None,
        "--project-name",
        "-p",
        help="Project name for the Docker image",
    ),
    postgres_version: str | None = typer.Option(
        None,
        "--postgres-version",
        help="PostgreSQL version (15-18)",
    ),
    output: Path = typer.Option(
        Path("docker-compose.yaml"),
        "--output",
        "-o",
        help="Output file path",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Overwrite existing file without prompting",
    ),
) -> None:
    """Create a Docker Compose configuration file for development or production.

    Generates a docker-compose.yaml file with all required services:
    - Development: web, db (PostgreSQL), docs
    - Production: web, db (PostgreSQL), nginx, certbot

    Examples:
        phoxtail docker create compose
        phoxtail docker create compose development -p mysite
        phoxtail docker create compose production --postgres-version 17
    """
    if environment is None:
        environment = questionary.select(
            "Select environment type:",
            choices=["development", "production"],
        ).ask()

        if environment is None:
            console.print("\n[dim]Cancelled.[/dim]")
            raise typer.Exit(0)

    env_lower = environment.lower()
    if env_lower not in ["development", "production"]:
        console.print(
            f"[red]Error:[/red] Invalid environment '{environment}'. "
            "Must be 'development' or 'production'."
        )
        raise typer.Exit(1)

    if output.exists() and not force:
        if not Confirm.ask(
            f"[yellow]Warning:[/yellow] {output} already exists. Overwrite?",
            default=False,
        ):
            console.print("[dim]Cancelled.[/dim]")
            raise typer.Exit(0)

    if project_name is None:
        console.print("\n[bold]Docker Configuration:[/bold]")
        project_name = Prompt.ask(
            "Project name for Docker image",
            default=get_project_name(),
        )

    project_name = project_name.lower().strip().replace(" ", "-")

    if postgres_version is None:
        postgres_version = questionary.select(
            "Select PostgreSQL version:",
            choices=POSTGRES_VERSIONS,
            default="18",
        ).ask()

        if postgres_version is None:
            console.print("\n[dim]Cancelled.[/dim]")
            raise typer.Exit(0)
    elif postgres_version not in POSTGRES_VERSIONS:
        console.print(
            f"[red]Error:[/red] Invalid PostgreSQL version '{postgres_version}'. "
            f"Must be one of: {', '.join(POSTGRES_VERSIONS)}"
        )
        raise typer.Exit(1)

    try:
        context = {
            "environment": env_lower,
            "image_name": f"{IMAGE_PREFIX}/{project_name}:latest",
            "postgres_version": postgres_version,
            "pg_data_path": _get_postgres_data_path(postgres_version),
            "requires_celery": any_app_requires_celery(),
        }
        if env_lower == "development":
            context["phoxtail_source"] = _get_phoxtail_source()

        content = render_template("docker/docker-compose.yaml", context)
        output.write_text(content)
        console.print(
            f"\n[green]✓[/green] Docker Compose file created: [bold]{output}[/bold]"
        )
        console.print(f"[dim]Image:[/dim] {IMAGE_PREFIX}/{project_name}:latest")
        console.print(f"[dim]PostgreSQL version:[/dim] {postgres_version}")
        console.print(f"[dim]Environment:[/dim] {env_lower}")

    except KeyboardInterrupt:
        console.print("\n[dim]Cancelled.[/dim]")
        raise typer.Exit(0)
    except Exception as e:
        console.print(f"[red]Error creating Docker Compose file:[/red] {e}")
        raise typer.Exit(1)
