"""Docker-related commands: lifecycle and file generation."""

import os
import subprocess
import sys
from pathlib import Path

import questionary
import typer
import yaml
from rich.console import Console
from rich.prompt import Confirm, Prompt

from phoxtail.cli.utils.config import (
    get_docker_registry,
    get_project_name,
    slugify,
)
from phoxtail.cli.utils.docker import collect_package_compose_fragments, docker_env
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
    detach: bool = typer.Option(False, "--detach", "-d", help="Run in background (detached)"),
    build: bool = typer.Option(False, "--build", "-b", help="Build images before starting"),
) -> None:
    """Start Docker services.

    Extra arguments are passed through to docker compose up.

    Examples:
        phoxtail docker up
        phoxtail docker up --detach
        phoxtail docker up --build
        phoxtail docker up --scale web=2
    """
    env = docker_env()

    if build:
        # Build first with explicit SSH socket so the build works regardless
        # of the SSH agent implementation (e.g. GNOME Keyring).
        build_cmd = ["docker", "compose", "build"]
        ssh_sock = os.environ.get("SSH_AUTH_SOCK")
        if ssh_sock:
            build_cmd += ["--ssh", f"default={ssh_sock}"]
        rc = subprocess.call(build_cmd, env=env)
        if rc != 0:
            sys.exit(rc)

    cmd = ["docker", "compose", "up"]
    if detach:
        cmd.append("-d")
    cmd.extend(ctx.args)
    sys.exit(subprocess.call(cmd, env=env))


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


def _git_sha() -> str | None:
    result = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True)
    return result.stdout.strip() if result.returncode == 0 else None


def _build_image(base: str, sha: str) -> int:
    """Build production image tagged as <base>:latest and <base>:<sha>."""
    cmd = ["docker", "build", "--target", "production"]
    ssh_sock = os.environ.get("SSH_AUTH_SOCK")
    if ssh_sock:
        cmd += ["--ssh", f"default={ssh_sock}"]
    cmd += ["-t", f"{base}:latest", "-t", f"{base}:{sha}", "."]
    return subprocess.call(cmd)


def _push_image(base: str, sha: str) -> int:
    """Push <base>:latest and <base>:<sha> to the registry."""
    rc = subprocess.call(["docker", "push", f"{base}:latest"])
    if rc != 0:
        return rc
    return subprocess.call(["docker", "push", f"{base}:{sha}"])


def _registry_and_sha() -> tuple[str, str] | None:
    """Resolve the image base and git SHA; prints errors and returns None on failure."""
    docker_registry = get_docker_registry()
    if not docker_registry:
        console.print(
            "[red]Error:[/red] [bold]\\[docker] registry[/bold] is not set in phoxtail.toml.\n"
            "  Add it:\n\n"
            "  [dim]\\[docker]\n"
            '  registry = "ghcr.io/<org_name>"[/dim]'
        )
        return None
    sha = _git_sha()
    if sha is None:
        console.print("[red]Error:[/red] Could not read git SHA — is this a git repository?")
        return None
    base = f"{docker_registry}/{slugify(get_project_name())}"
    return base, sha


@app.command("login")
def login_cmd(
    username: str | None = typer.Option(None, "--username", "-u", help="Registry username"),
    token: str | None = typer.Option(
        None,
        "--token",
        help="Registry token / PAT (omit to be prompted; use PHOXTAIL_REGISTRY_TOKEN in CI)",
        envvar="PHOXTAIL_REGISTRY_TOKEN",
    ),
) -> None:
    """Authenticate to the project's configured Docker registry.

    Reads the registry host from phoxtail.toml and runs docker login.
    Prompts interactively for any credentials not supplied as flags.
    In CI, set PHOXTAIL_REGISTRY_TOKEN to avoid the interactive prompt.

    For GHCR, use your GitHub username and a PAT with write:packages scope.

    Examples:
        phoxtail docker login
        phoxtail docker login --username alice
        phoxtail docker login --username alice --token ghp_...
    """
    docker_registry = get_docker_registry()
    if not docker_registry:
        console.print(
            "[red]Error:[/red] [bold]\\[docker] registry[/bold] is not set in phoxtail.toml.\n"
            "  Add it:\n\n"
            "  [dim]\\[docker]\n"
            '  registry = "ghcr.io/<org_name>"[/dim]'
        )
        raise typer.Exit(1)

    host = docker_registry.split("/")[0]
    console.print(f"\nLogging in to [bold]{host}[/bold]")

    if username is None:
        username = questionary.text("Username:").ask()
        if username is None:
            console.print("\n[dim]Cancelled.[/dim]")
            raise typer.Exit(0)
    if token is None:
        token = questionary.password("Token:").ask()
        if token is None:
            console.print("\n[dim]Cancelled.[/dim]")
            raise typer.Exit(0)

    username = username.strip()
    token = token.strip()

    if not username:
        console.print("[red]Error:[/red] Username cannot be empty")
        raise typer.Exit(1)
    if not token:
        console.print("[red]Error:[/red] Token cannot be empty")
        raise typer.Exit(1)

    try:
        with console.status("Authenticating…", spinner="dots"):
            result = subprocess.run(
                ["docker", "login", host, "-u", username, "--password-stdin"],
                input=token,
                text=True,
                capture_output=True,
                timeout=30,
            )
    except subprocess.TimeoutExpired:
        console.print(f"[red]Error:[/red] timed out connecting to [bold]{host}[/bold]")
        raise typer.Exit(1)

    if result.returncode == 0:
        console.print(f"[green]✓[/green] Logged in to [bold]{host}[/bold]")
    else:
        detail = "\n".join(line for line in (result.stderr.strip(), result.stdout.strip()) if line)
        console.print(f"[red]Error:[/red] docker login failed\n{detail}")
        raise typer.Exit(result.returncode)


@app.command("build")
def build_cmd() -> None:
    """Build the production Docker image, tagged as :latest and :<git-sha>.

    Uses SSH agent forwarding so private git dependencies can be cloned
    during the build.

    Examples:
        phoxtail docker build
    """
    result = _registry_and_sha()
    if result is None:
        raise typer.Exit(1)
    base, sha = result
    console.print(f"\n  [bold cyan]→[/bold cyan] Building [bold]{base}[/bold] ({sha})")
    rc = _build_image(base, sha)
    if rc != 0:
        raise typer.Exit(rc)
    console.print(f"  [green]✓[/green] Built: {base}:latest, {base}:{sha}")


@app.command("push")
def push_cmd() -> None:
    """Push the production image (:latest and :<git-sha>) to the configured registry.

    Assumes the image has already been built locally (run ``phoxtail docker build`` first).

    Examples:
        phoxtail docker push
    """
    result = _registry_and_sha()
    if result is None:
        raise typer.Exit(1)
    base, sha = result
    console.print(f"\n  [bold cyan]→[/bold cyan] Pushing [bold]{base}:latest[/bold] and [bold]{base}:{sha}[/bold]")
    rc = _push_image(base, sha)
    if rc != 0:
        raise typer.Exit(rc)
    console.print(f"  [green]✓[/green] Pushed: {base}:latest, {base}:{sha}")


@app.command("release")
def release_cmd() -> None:
    """Build and push the production image in one step (build + push).

    Equivalent to running ``phoxtail docker build`` followed by ``phoxtail docker push``.

    Examples:
        phoxtail docker release
    """
    result = _registry_and_sha()
    if result is None:
        raise typer.Exit(1)
    base, sha = result

    console.print(f"\n  [bold cyan]→[/bold cyan] Building [bold]{base}[/bold] ({sha})")
    rc = _build_image(base, sha)
    if rc != 0:
        raise typer.Exit(rc)
    console.print("  [green]✓[/green] Built")

    console.print("\n  [bold cyan]→[/bold cyan] Pushing")
    rc = _push_image(base, sha)
    if rc != 0:
        raise typer.Exit(rc)
    console.print(f"  [green]✓[/green] Released: {base}:latest, {base}:{sha}")


# Valid versions for selection
PYTHON_VERSIONS = ["3.11", "3.12", "3.13"]
POSTGRES_VERSIONS = ["15", "16", "17", "18"]

IMAGE_PREFIX = slugify(get_project_name())


def _get_postgres_data_path(version: str) -> str:
    """Get the PostgreSQL data directory path for a given version.

    PostgreSQL 18+ uses /var/lib/postgresql (version-specific subdirs).
    PostgreSQL 17 and below use /var/lib/postgresql/data.
    """
    return "/var/lib/postgresql" if int(version) >= 18 else "/var/lib/postgresql/data"


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
            default="3.13",
        ).ask()

        if python_version is None:
            console.print("\n[dim]Cancelled.[/dim]")
            raise typer.Exit(0)
    elif python_version not in PYTHON_VERSIONS:
        console.print(
            f"[red]Error:[/red] Invalid Python version '{python_version}'. Must be one of: {', '.join(PYTHON_VERSIONS)}"
        )
        raise typer.Exit(1)

    if port < 1 or port > 65535:
        console.print(f"[red]Error:[/red] Invalid port '{port}'. Must be between 1 and 65535")
        raise typer.Exit(1)

    if gunicorn_workers < 1:
        console.print(f"[red]Error:[/red] Invalid worker count '{gunicorn_workers}'. Must be at least 1")
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

        # A Dockerfile without a matching .dockerignore is always wrong in
        # this project layout (runtime state dirs like certbot/, media/,
        # static/, db-backups/ live alongside code), so emit it here too.
        ignore_path = output.parent / ".dockerignore"
        if not ignore_path.exists() or force:
            ignore_path.write_text(render_template("docker/dockerignore", {}))
            console.print(f"[green]✓[/green] .dockerignore created: [bold]{ignore_path}[/bold]")
    except KeyboardInterrupt:
        console.print("\n[dim]Cancelled.[/dim]")
        raise typer.Exit(0)
    except Exception as e:
        console.print(f"[red]Error creating Dockerfile:[/red] {e}")
        raise typer.Exit(1)


@create_app.command("dockerignore")
def dockerignore(
    output: Path = typer.Option(
        Path(".dockerignore"),
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
    """Create a .dockerignore file.

    Excludes runtime state (certbot, media, static, db-backups), secrets,
    VCS and cache dirs from the Docker build context. This is generated
    automatically by ``phoxtail docker create dockerfile`` — use this
    command to regenerate it standalone.

    Examples:
        phoxtail docker create dockerignore
        phoxtail docker create dockerignore --force
    """
    if output.exists() and not force:
        if not Confirm.ask(
            f"[yellow]Warning:[/yellow] {output} already exists. Overwrite?",
            default=False,
        ):
            console.print("[dim]Cancelled.[/dim]")
            raise typer.Exit(0)

    try:
        output.write_text(render_template("docker/dockerignore", {}))
        console.print(f"[green]✓[/green] .dockerignore created: [bold]{output}[/bold]")
    except Exception as e:
        console.print(f"[red]Error creating .dockerignore:[/red] {e}")
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
    registry: bool = typer.Option(
        False,
        "--registry",
        help="Registry-pull mode: no build block, named static/media volumes. Requires production.",
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
        console.print(f"[red]Error:[/red] Invalid environment '{environment}'. Must be 'development' or 'production'.")
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
            default=slugify(get_project_name()),
        )

    project_name = slugify(project_name.strip())

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

    if registry and env_lower != "production":
        console.print("[red]Error:[/red] --registry requires production environment.")
        raise typer.Exit(1)

    if registry:
        docker_registry = get_docker_registry()
        if not docker_registry:
            console.print(
                "[red]Error:[/red] [bold]\\[docker] registry[/bold] is not set in phoxtail.toml.\n"
                "  Add it before using --registry:\n\n"
                '  [dim]\\[docker]\\nregistry = "ghcr.io/yourorg"[/dim]'
            )
            raise typer.Exit(1)
        image_name = f"{docker_registry}/{project_name}:latest"
    else:
        image_name = f"{IMAGE_PREFIX}/{project_name}:latest"

    try:
        context = {
            "environment": env_lower,
            "image_name": image_name,
            "postgres_version": postgres_version,
            "pg_data_path": _get_postgres_data_path(postgres_version),
            "registry_mode": registry,
        }

        if Path(".venv").exists():
            with console.status("[dim]Syncing .venv before scanning fragments…[/dim]"):
                sync = subprocess.run(["uv", "sync"], capture_output=True, text=True)
            if sync.returncode != 0:
                console.print(
                    f"[yellow]Warning:[/yellow] uv sync failed — fragments may be stale\n{sync.stderr.strip()}"
                )

        base = yaml.safe_load(render_template("docker/docker-compose.yaml", context))
        fragments = collect_package_compose_fragments(context)
        if fragments["services"]:
            base.setdefault("services", {}).update(fragments["services"])
        if fragments["volumes"]:
            base.setdefault("volumes", {}).update(fragments["volumes"])
        content = yaml.dump(base, default_flow_style=False, sort_keys=False, allow_unicode=True)
        output.write_text(content)
        console.print(f"\n[green]✓[/green] Docker Compose file created: [bold]{output}[/bold]")
        if fragments["services"]:
            console.print(f"[dim]App fragments merged:[/dim] {', '.join(fragments['services'].keys())}")
        console.print(f"[dim]Image:[/dim] {image_name}")
        console.print(f"[dim]PostgreSQL version:[/dim] {postgres_version}")
        console.print(f"[dim]Environment:[/dim] {env_lower}")
        if registry:
            console.print("[dim]Mode:[/dim] registry-pull (no local build)")

    except KeyboardInterrupt:
        console.print("\n[dim]Cancelled.[/dim]")
        raise typer.Exit(0)
    except Exception as e:
        console.print(f"[red]Error creating Docker Compose file:[/red] {e}")
        raise typer.Exit(1)
