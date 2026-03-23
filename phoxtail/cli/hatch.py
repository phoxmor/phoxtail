"""Scaffold a new Phoxtail project."""

import shutil
import subprocess
import sys
from pathlib import Path

import questionary
import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm

from phoxtail.cli.utils.config import validate_project_name
from phoxtail.cli.utils.templates import render_template

console = Console()

PLACEHOLDER = "{{ phoxtail_project_name }}"
TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "project_template"


def _copy_template(project_name: str, target_dir: Path) -> int:
    """Copy project_template into target_dir, replacing placeholders.

    Uses str.replace() for substitution — NOT Jinja2 — because scaffold
    files contain Django template syntax that must be left untouched.

    Returns the number of files copied.
    """
    if not TEMPLATE_DIR.is_dir():
        raise FileNotFoundError(
            f"Template directory not found at: {TEMPLATE_DIR}\n"
            "The hatch command requires phoxtail[engine] or an editable "
            "install of the full repository."
        )

    file_count = 0
    for src_path in sorted(TEMPLATE_DIR.rglob("*")):
        if src_path.is_dir():
            continue

        rel_path = src_path.relative_to(TEMPLATE_DIR)
        dest_path = target_dir / rel_path
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        # Try text replacement; fall back to binary copy for non-text files
        try:
            content = src_path.read_text(encoding="utf-8")
            if PLACEHOLDER in content:
                content = content.replace(PLACEHOLDER, project_name)
            dest_path.write_text(content, encoding="utf-8")
        except UnicodeDecodeError:
            shutil.copy2(src_path, dest_path)

        file_count += 1

    return file_count


def _run_step(target_dir: Path, args: list[str]) -> bool:
    """Run a phoxtail CLI command as a subprocess in the target directory.

    Returns True if the command succeeded.
    """
    result = subprocess.run(
        [sys.executable, "-m", "phoxtail", *args],
        cwd=target_dir,
    )
    if result.returncode != 0:
        console.print(
            f"  [yellow]⚠[/yellow]  Command exited with code {result.returncode}"
        )
        return False
    return True


def _run_wizard(target_dir: Path) -> set[str]:
    """Walk the user through optional post-scaffold setup steps.

    Each step invokes an existing phoxtail CLI command as a subprocess
    inside the new project directory (which has a phoxtail.toml).
    Steps are optional — the user can skip any of them.

    The environment type (development/production) is asked once and
    reused across steps that need it.

    Returns a set of completed step names for the summary panel.
    """
    console.print(
        Panel(
            "The setup wizard will walk you through configuring your new project.\n"
            "Each step is optional — skip any and run the commands later.",
            title="[bold cyan]Project Setup[/bold cyan]",
            border_style="cyan",
            expand=False,
        )
    )

    # Ask environment type once — reused by env create and docker compose
    environment = questionary.select(
        "Select environment type:",
        choices=["development", "production"],
    ).ask()
    if environment is None:
        console.print("[dim]Cancelled.[/dim]")
        return set()

    nginx_sub = "initial" if environment == "development" else "production"

    completed = set()

    # Step 1: Environment
    console.print("\n[bold]Step 1/5: Environment[/bold]")
    console.print(f"  Generate {environment} .env configuration")
    if Confirm.ask(
        f"  Run [cyan]phoxtail env create {environment}[/cyan]?", default=True
    ):
        console.print()
        if _run_step(target_dir, ["env", "create", environment]):
            completed.add("env")
    else:
        console.print("  [dim]Skipped.[/dim]")

    # Step 2: Dockerfile
    console.print("\n[bold]Step 2/5: Dockerfile[/bold]")
    console.print("  Generate Dockerfile")
    if Confirm.ask(
        "  Run [cyan]phoxtail docker create dockerfile[/cyan]?", default=True
    ):
        console.print()
        if _run_step(target_dir, ["docker", "create", "dockerfile"]):
            completed.add("dockerfile")
    else:
        console.print("  [dim]Skipped.[/dim]")

    # Step 3: docker-compose.yaml
    console.print("\n[bold]Step 3/5: Docker Compose[/bold]")
    console.print(f"  Generate {environment} docker-compose.yaml")
    if Confirm.ask(
        f"  Run [cyan]phoxtail docker create compose {environment}[/cyan]?",
        default=True,
    ):
        console.print()
        if _run_step(target_dir, ["docker", "create", "compose", environment]):
            completed.add("compose")
    else:
        console.print("  [dim]Skipped.[/dim]")

    # Step 4: Nginx
    console.print("\n[bold]Step 4/5: Nginx[/bold]")
    console.print(f"  Generate {nginx_sub} nginx.conf")
    if Confirm.ask(
        f"  Run [cyan]phoxtail nginx create {nginx_sub}[/cyan]?", default=True
    ):
        console.print()
        if _run_step(target_dir, ["nginx", "create", nginx_sub]):
            completed.add("nginx")
    else:
        console.print("  [dim]Skipped.[/dim]")

    # Step 5: Launch app
    console.print("\n[bold]Step 5/5: Launch App[/bold]")
    console.print("  Build images and start the application")
    if Confirm.ask("  Launch the app?", default=True):
        detach = Confirm.ask("  Run in background (detached)?", default=False)
        console.print()
        args = ["docker", "up", "--build"]
        if not detach:
            args.append("--no-detach")
        if _run_step(target_dir, args):
            completed.add("docker_up")
            if detach:
                console.print(
                    "\n  [green]✓[/green] App is running at "
                    "[bold cyan]http://localhost[/bold cyan]"
                )
    else:
        console.print("  [dim]Skipped.[/dim]")

    return completed


def hatch(
    project_name: str = typer.Argument(
        ...,
        help="Name for the new project (must be a valid Python identifier)",
    ),
    output_dir: Path = typer.Option(
        Path("."),
        "--output-dir",
        "-o",
        help="Parent directory to create the project in",
    ),
    no_wizard: bool = typer.Option(
        False,
        "--no-wizard",
        help="Skip the interactive setup wizard",
    ),
) -> None:
    """Hatch a new Phoxtail project.

    Scaffolds a Django/Wagtail project with opinionated defaults — a custom
    User model, Wagtail page types, design tokens, and the streams block
    system. The generated code is yours to modify.

    After scaffolding, an optional wizard walks you through environment,
    Docker, and nginx setup using the existing CLI commands.

    Examples:
        phoxtail hatch myproject
        phoxtail hatch myproject --output-dir /tmp
        phoxtail hatch myproject --no-wizard
    """
    # Validate project name
    error = validate_project_name(project_name)
    if error:
        console.print(f"[red]Error:[/red] {error}")
        raise typer.Exit(1)

    target_dir = (output_dir / project_name).resolve()

    # Check for existing directory
    if target_dir.exists():
        if not Confirm.ask(
            f"[yellow]Warning:[/yellow] '{target_dir}' already exists. Overwrite?",
            default=False,
        ):
            console.print("[dim]Cancelled.[/dim]")
            raise typer.Exit(0)
        shutil.rmtree(target_dir)

    try:
        console.print(
            f"\n[bold cyan]Hatching project [white]'{project_name}'"
            "[/white]...[/bold cyan]\n"
        )

        # Copy template files with placeholder replacement
        target_dir.mkdir(parents=True, exist_ok=True)
        file_count = _copy_template(project_name, target_dir)

        # Generate requirements.in from template
        requirements_in = render_template("requirements/requirements.in", {})
        (target_dir / "requirements.in").write_text(requirements_in, encoding="utf-8")
        file_count += 1

        # Compile requirements.in → requirements.txt
        console.print("[dim]Compiling requirements.in → requirements.txt...[/dim]")
        if _run_step(target_dir, ["requirements", "compile"]):
            console.print("[green]✓[/green] Requirements compiled successfully\n")
        else:
            # Fallback: copy requirements.in as requirements.txt
            console.print(
                "[yellow]⚠[/yellow]  Could not compile requirements. "
                "Run [cyan]phoxtail requirements compile[/cyan] manually.\n"
            )
            shutil.copy2(
                target_dir / "requirements.in",
                target_dir / "requirements.txt",
            )

        console.print(
            f"[green]✓[/green] Scaffolded {file_count} files into "
            f"[bold]{target_dir}[/bold]\n"
        )

        # Run the setup wizard unless --no-wizard
        completed = set()
        if not no_wizard:
            run_wizard = Confirm.ask(
                "Would you like to run the setup wizard?", default=True
            )
            if run_wizard:
                completed = _run_wizard(target_dir)

        # Build context-aware next steps
        next_steps = []
        if "env" not in completed:
            next_steps.append(
                "  • Run [cyan]phoxtail env create[/cyan] to generate .env"
            )
        if "dockerfile" not in completed or "compose" not in completed:
            next_steps.append(
                "  • Run [cyan]phoxtail docker create dockerfile[/cyan] "
                "and [cyan]compose[/cyan]"
            )
        if "nginx" not in completed:
            next_steps.append(
                "  • Run [cyan]phoxtail nginx create initial[/cyan] for nginx"
            )
        if "docker_up" not in completed:
            next_steps.append(
                "  • Run [cyan]phoxtail docker up --build[/cyan] to launch the app"
            )

        console.print(
            Panel(
                f"[green]Project '{project_name}' is ready![/green]\n\n"
                f"  cd {target_dir}\n\n"
                "Next steps:\n" + "\n".join(next_steps),
                title="[bold green]Done[/bold green]",
                border_style="green",
                expand=False,
            )
        )

    except KeyboardInterrupt:
        console.print("\n[dim]Cancelled.[/dim]")
        raise typer.Exit(0)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)
