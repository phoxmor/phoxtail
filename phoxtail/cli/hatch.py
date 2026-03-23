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

# Wizard step definitions: (key, label)
WIZARD_STEPS = [
    ("env", "Environment"),
    ("dockerfile", "Dockerfile"),
    ("compose", "Docker Compose"),
    ("nginx", "Nginx"),
    ("superuser", "Create Superuser"),
    ("docker_up", "Launch App"),
]

# Status icons
_ICONS = {
    "done": "[green]✓[/green]",
    "failed": "[red]✗[/red]",
    "skipped": "[dim]⏭[/dim]",
    "current": "[bold cyan]▸[/bold cyan]",
    "pending": "[dim]○[/dim]",
}


def _step_status_line(index: int, label: str, status: str, detail: str = "") -> str:
    icon = _ICONS[status]
    num = f"{index + 1}."
    suffix = f"  [dim]{detail}[/dim]" if detail else ""
    if status == "current":
        return f"  {icon} [bold]{num} {label}[/bold]{suffix}"
    return f"  {icon} {num} {label}{suffix}"


def _render_progress(
    project_name: str,
    steps: dict[str, str],
    details: dict[str, str],
    current_index: int | None = None,
) -> Panel:
    """Build the progress panel showing all wizard steps."""
    lines = []
    for i, (key, label) in enumerate(WIZARD_STEPS):
        if key in steps:
            status = steps[key]
        elif current_index is not None and i == current_index:
            status = "current"
        else:
            status = "pending"
        lines.append(_step_status_line(i, label, status, details.get(key, "")))

    return Panel(
        "\n".join(lines),
        title=f"[bold cyan]Hatching '{project_name}'[/bold cyan]",
        border_style="cyan",
        expand=False,
    )


def _clear_and_show_progress(
    project_name: str,
    steps: dict[str, str],
    details: dict[str, str],
    current_index: int | None = None,
    pause: bool = False,
) -> None:
    """Clear the terminal and redraw the progress panel.

    If pause=True (previous step failed), waits so the user can read
    the subprocess output before clearing.
    """
    if pause:
        console.print()
        console.input("[dim]Press Enter to continue...[/dim]")
    console.clear()
    console.print()
    console.print(_render_progress(project_name, steps, details, current_index))
    console.print()


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
    return result.returncode == 0


def _run_wizard(project_name: str, target_dir: Path) -> dict[str, str]:
    """Walk the user through optional post-scaffold setup steps.

    Each step invokes an existing phoxtail CLI command as a subprocess
    inside the new project directory (which has a phoxtail.toml).
    Steps are optional — the user can skip any of them.

    The environment type (development/production) is asked once and
    reused across steps that need it.

    Returns a dict mapping step keys to their status ("done"/"skipped"/"failed").
    """
    steps: dict[str, str] = {}  # key -> "done" | "skipped" | "failed"
    details: dict[str, str] = {}  # key -> detail text

    # Show initial progress with all steps pending
    _clear_and_show_progress(project_name, steps, details, current_index=None)

    # Ask environment type once — reused by env create and docker compose
    environment = questionary.select(
        "Select environment type:",
        choices=["development", "production"],
    ).ask()
    if environment is None:
        console.print("[dim]Cancelled.[/dim]")
        return {}

    nginx_sub = "initial" if environment == "development" else "production"
    prev_failed = False

    # --- Step 1: Environment ---
    _clear_and_show_progress(
        project_name, steps, details, current_index=0, pause=prev_failed
    )
    console.print(f"  Generate [bold]{environment}[/bold] .env configuration\n")
    if Confirm.ask(
        f"  Run [cyan]phoxtail env create {environment}[/cyan]?", default=True
    ):
        if _run_step(target_dir, ["env", "create", environment]):
            steps["env"] = "done"
            details["env"] = environment
            prev_failed = False
        else:
            steps["env"] = "failed"
            details["env"] = "command failed"
            prev_failed = True
    else:
        steps["env"] = "skipped"
        prev_failed = False

    # --- Step 2: Dockerfile ---
    _clear_and_show_progress(
        project_name, steps, details, current_index=1, pause=prev_failed
    )
    console.print("  Generate Dockerfile\n")
    if Confirm.ask(
        "  Run [cyan]phoxtail docker create dockerfile[/cyan]?", default=True
    ):
        if _run_step(target_dir, ["docker", "create", "dockerfile"]):
            steps["dockerfile"] = "done"
            prev_failed = False
        else:
            steps["dockerfile"] = "failed"
            details["dockerfile"] = "command failed"
            prev_failed = True
    else:
        steps["dockerfile"] = "skipped"
        prev_failed = False

    # --- Step 3: Docker Compose ---
    _clear_and_show_progress(
        project_name, steps, details, current_index=2, pause=prev_failed
    )
    console.print(f"  Generate [bold]{environment}[/bold] docker-compose.yaml\n")
    if Confirm.ask(
        f"  Run [cyan]phoxtail docker create compose {environment}[/cyan]?",
        default=True,
    ):
        if _run_step(target_dir, ["docker", "create", "compose", environment]):
            steps["compose"] = "done"
            details["compose"] = environment
            prev_failed = False
        else:
            steps["compose"] = "failed"
            details["compose"] = "command failed"
            prev_failed = True
    else:
        steps["compose"] = "skipped"
        prev_failed = False

    # --- Step 4: Nginx ---
    _clear_and_show_progress(
        project_name, steps, details, current_index=3, pause=prev_failed
    )
    console.print(f"  Generate [bold]{nginx_sub}[/bold] nginx.conf\n")
    if Confirm.ask(
        f"  Run [cyan]phoxtail nginx create {nginx_sub}[/cyan]?", default=True
    ):
        if _run_step(target_dir, ["nginx", "create", nginx_sub]):
            steps["nginx"] = "done"
            details["nginx"] = nginx_sub
            prev_failed = False
        else:
            steps["nginx"] = "failed"
            details["nginx"] = "command failed"
            prev_failed = True
    else:
        steps["nginx"] = "skipped"
        prev_failed = False

    # --- Step 5: Create Superuser ---
    _clear_and_show_progress(
        project_name, steps, details, current_index=4, pause=prev_failed
    )
    console.print("  Create an admin superuser account\n")
    if Confirm.ask(
        "  Run [cyan]phoxtail manage createsuperuser[/cyan]?", default=True
    ):
        # Migrate first — the user table must exist before createsuperuser
        with console.status("  [bold cyan]Preparing database…[/bold cyan]"):
            migrate_result = subprocess.run(
                [sys.executable, "-m", "phoxtail", "manage", "migrate"],
                cwd=target_dir,
                capture_output=True,
                text=True,
            )
            migrate_ok = migrate_result.returncode == 0
        if not migrate_ok:
            console.print("  [red]Database migration failed.[/red]")
            if migrate_result.stderr:
                console.print(f"  [dim]{migrate_result.stderr.strip()}[/dim]")
            steps["superuser"] = "failed"
            details["superuser"] = "migration failed"
            prev_failed = True
        else:
            console.print()
            if _run_step(target_dir, ["manage", "createsuperuser"]):
                steps["superuser"] = "done"
                prev_failed = False
            else:
                steps["superuser"] = "failed"
                details["superuser"] = "command failed"
                prev_failed = True
        # Clean up containers started by docker compose run (e.g. db)
        subprocess.run(
            ["docker", "compose", "down"],
            cwd=target_dir,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    else:
        steps["superuser"] = "skipped"
        prev_failed = False

    # --- Step 6: Launch App ---
    _clear_and_show_progress(
        project_name, steps, details, current_index=5, pause=prev_failed
    )
    console.print("  Build images and start the application\n")
    if Confirm.ask("  Launch the app?", default=True):
        detach = Confirm.ask("  Run in background (detached)?", default=False)
        args = ["docker", "up", "--build"]
        if not detach:
            args.append("--no-detach")
        if _run_step(target_dir, args):
            steps["docker_up"] = "done"
            details["docker_up"] = "detached" if detach else "foreground"
            prev_failed = False
        else:
            steps["docker_up"] = "failed"
            details["docker_up"] = "command failed"
            prev_failed = True
    else:
        steps["docker_up"] = "skipped"
        prev_failed = False

    # Show final state
    _clear_and_show_progress(
        project_name, steps, details, pause=prev_failed
    )

    return steps


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
        console.print()

        # Copy template files with placeholder replacement
        target_dir.mkdir(parents=True, exist_ok=True)
        with console.status(
            f"[bold cyan]Scaffolding '{project_name}'...[/bold cyan]"
        ):
            file_count = _copy_template(project_name, target_dir)

            # Generate requirements.in from template
            requirements_in = render_template("requirements/requirements.in", {})
            (target_dir / "requirements.in").write_text(
                requirements_in, encoding="utf-8"
            )
            file_count += 1

            # Compile requirements.in → requirements.txt (quiet — no user interaction)
            compiled = subprocess.run(
                [sys.executable, "-m", "phoxtail", "requirements", "compile"],
                cwd=target_dir,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            if compiled.returncode != 0:
                shutil.copy2(
                    target_dir / "requirements.in",
                    target_dir / "requirements.txt",
                )

        # Summary
        req_note = (
            ""
            if compiled.returncode == 0
            else (
                "\n[yellow]⚠[/yellow] requirements not compiled"
                " — run [cyan]phoxtail requirements compile[/cyan]"
            )
        )
        console.print(
            Panel(
                f"[green]Project '{project_name}' created[/green] "
                f"at [bold]{target_dir}[/bold]"
                + req_note,
                border_style="green",
                expand=False,
            )
        )
        console.print()

        # Run the setup wizard unless --no-wizard
        wizard_steps: dict[str, str] = {}
        if not no_wizard:
            run_wizard = Confirm.ask(
                "Would you like to run the setup wizard?", default=True
            )
            if run_wizard:
                wizard_steps = _run_wizard(project_name, target_dir)

        # Build context-aware next steps — separate skipped from failed
        next_steps = []
        failed_steps = []

        def _check(
            key: str, cmd: str, note: str = "",
        ) -> None:
            status = wizard_steps.get(key)
            hint = f"\n    [dim]{note}[/dim]" if note else ""
            if status == "failed":
                failed_steps.append(f"  • [cyan]{cmd}[/cyan]{hint}")
            elif status != "done":
                next_steps.append(f"  • [cyan]{cmd}[/cyan]{hint}")

        _check("env", "phoxtail env create",
               "generate .env configuration")
        _check("dockerfile", "phoxtail docker create dockerfile",
               "generate Dockerfile")
        _check("compose", "phoxtail docker create compose",
               "generate docker-compose.yaml")
        _check("nginx", "phoxtail nginx create initial",
               "optional — only needed for production-like setups")
        _check("superuser", "phoxtail manage createsuperuser",
               "create an admin superuser account")
        _check("docker_up", "phoxtail docker up --build",
               "build images and start the application")

        # Assemble next steps
        all_steps = [
            f"  • [cyan]cd {target_dir}[/cyan]"
            "\n    [dim]navigate to the project directory[/dim]"
        ]
        if failed_steps:
            all_steps.append("")
            all_steps.append("  [bold red]Failed (retry):[/bold red]")
            all_steps.extend(failed_steps)
        if next_steps:
            all_steps.extend(next_steps)

        if not failed_steps and not next_steps:
            console.print(
                Panel(
                    f"[green]'{project_name}' is ready![/green]",
                    border_style="green",
                    expand=False,
                )
            )
        else:
            border = "yellow" if failed_steps else "green"
            console.print(
                Panel(
                    "[bold]Next steps:[/bold]\n" + "\n".join(all_steps),
                    border_style=border,
                    expand=False,
                )
            )

    except KeyboardInterrupt:
        console.print("\n[dim]Cancelled.[/dim]")
        raise typer.Exit(0)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)
