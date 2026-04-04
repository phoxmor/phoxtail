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
from phoxtail.cli.utils.docker import docker_env
from phoxtail.cli.utils.templates import render_template

console = Console()

PLACEHOLDER = "{{ phoxtail_project_name }}"
APPS_MARKER = "    # {{ phoxtail_optional_apps }}\n"
CTX_MARKER = "                # {{ phoxtail_context_processors }}\n"
URLS_MARKER = "    # {{ phoxtail_optional_urls }}\n"
TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "project_template"

# Optional phoxtail apps available during hatching.
OPTIONAL_APPS = [
    {"name": "Blog", "value": "phoxtail.blog"},
    {"name": "Dashboard", "value": "phoxtail.dashboard"},
    {"name": "Booking", "value": "phoxtail.booking"},
]

# App groups: selecting a single value expands into multiple INSTALLED_APPS entries.
APP_GROUPS = {
    "phoxtail.booking": [
        "phoxtail.booking.core",
        "phoxtail.booking.services",
        "phoxtail.booking.events",
        "phoxtail.booking.subscriptions",
        "phoxtail.booking.reservations",
    ],
}

# Implicit dependencies: selecting an app auto-includes its dependencies.
APP_DEPENDENCIES = {
    "phoxtail.booking": ["phoxtail.dashboard"],
}

# Context processors to inject when specific optional apps are selected.
APP_CONTEXT_PROCESSORS = {
    "phoxtail.dashboard": [
        "phoxtail.dashboard.context_processors.dashboard_nav",
    ],
}

# URL patterns to inject when specific optional apps are selected.
# Each value is a line of code to insert into urls.py (with correct indent).
APP_URL_PATTERNS = {
    "phoxtail.dashboard": (
        '    path("dashboard/", include("phoxtail.dashboard.urls")),\n'
    ),
}

# Wizard step definitions: (key, label)
WIZARD_STEPS = [
    ("env", "Environment"),
    ("dockerfile", "Dockerfile"),
    ("compose", "Docker Compose"),
    ("nginx", "Nginx"),
    ("migrate", "Migrate Database"),
    ("stream_engine", "Stream Engine"),
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
    wizard_steps: list[tuple[str, str]],
    environment: str,
    current_index: int | None = None,
) -> Panel:
    """Build the progress panel showing all wizard steps."""
    lines = []
    for i, (key, label) in enumerate(wizard_steps):
        if key in steps:
            status = steps[key]
        elif current_index is not None and i == current_index:
            status = "current"
        else:
            status = "pending"
        lines.append(_step_status_line(i, label, status, details.get(key, "")))

    return Panel(
        "\n".join(lines),
        title=(
            f"[bold cyan]Hatching '{project_name}'[/bold cyan] [dim]{environment}[/dim]"
        ),
        border_style="cyan",
        expand=False,
    )


def _clear_and_show_progress(
    project_name: str,
    steps: dict[str, str],
    details: dict[str, str],
    wizard_steps: list[tuple[str, str]],
    environment: str,
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
    console.print(
        _render_progress(
            project_name, steps, details, wizard_steps, environment, current_index
        )
    )
    console.print()


def _copy_template(
    project_name: str, target_dir: Path, optional_apps: list[str] | None = None
) -> int:
    """Copy project_template into target_dir, replacing placeholders.

    Uses str.replace() for substitution — NOT Jinja2 — because scaffold
    files contain Django template syntax that must be left untouched.

    *optional_apps* is a list of dotted app names to inject into
    INSTALLED_APPS (replacing the ``APPS_MARKER`` line).  When empty or
    ``None`` the marker is simply removed so the file stays clean.

    Returns the number of files copied.
    """
    if not TEMPLATE_DIR.is_dir():
        raise FileNotFoundError(
            f"Template directory not found at: {TEMPLATE_DIR}\n"
            "The hatch command requires phoxtail[engine] or an editable "
            "install of the full repository."
        )

    # Resolve implicit dependencies (e.g. booking requires dashboard).
    resolved_apps: list[str] = []
    for app in optional_apps or []:
        for dep in APP_DEPENDENCIES.get(app, []):
            if dep not in resolved_apps:
                resolved_apps.append(dep)
        if app not in resolved_apps:
            resolved_apps.append(app)

    # Expand app groups into individual INSTALLED_APPS entries.
    installed_apps: list[str] = []
    for app in resolved_apps:
        installed_apps.extend(APP_GROUPS.get(app, [app]))

    if installed_apps:
        apps_replacement = "".join(f'    "{app}",\n' for app in installed_apps)
    else:
        apps_replacement = ""

    # Collect context processors for selected/resolved apps.
    ctx_processors = []
    for app in resolved_apps:
        ctx_processors.extend(APP_CONTEXT_PROCESSORS.get(app, []))
    if ctx_processors:
        ctx_replacement = "".join(f'                "{cp}",\n' for cp in ctx_processors)
    else:
        ctx_replacement = ""

    # Collect URL patterns for selected/resolved apps.
    url_lines = []
    for app in resolved_apps:
        line = APP_URL_PATTERNS.get(app)
        if line:
            url_lines.append(line)
    urls_replacement = "".join(url_lines)

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
            if APPS_MARKER in content:
                content = content.replace(APPS_MARKER, apps_replacement)
            if CTX_MARKER in content:
                content = content.replace(CTX_MARKER, ctx_replacement)
            if URLS_MARKER in content:
                content = content.replace(URLS_MARKER, urls_replacement)
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


def _ensure_migrated(
    target_dir: Path,
    steps: dict[str, str],
    details: dict[str, str],
) -> bool:
    """Ensure the database is migrated, prompting if the migrate step was skipped.

    Returns True if the database is migrated (either previously or just now).
    """
    if steps.get("migrate") == "done":
        return True

    if steps.get("migrate") == "failed":
        console.print("  [red]Database migration previously failed.[/red]")
        if not Confirm.ask("  Retry migration now?", default=True):
            return False

    # Migration was skipped or needs retry — offer to run it
    if steps.get("migrate") == "skipped":
        console.print("  [yellow]This step requires a migrated database.[/yellow]")
        if not Confirm.ask("  Run migration now?", default=True):
            return False

    if _run_step(target_dir, ["manage", "migrate"]):
        steps["migrate"] = "done"
        return True

    steps["migrate"] = "failed"
    details["migrate"] = "command failed"
    return False


def _run_wizard(
    project_name: str, target_dir: Path, environment: str
) -> dict[str, str]:
    """Walk the user through optional post-scaffold setup steps.

    Each step invokes an existing phoxtail CLI command as a subprocess
    inside the new project directory (which has a phoxtail.toml).
    Steps are optional — the user can skip any of them.

    Returns a dict mapping step keys to their status ("done"/"skipped"/"failed").
    """
    steps: dict[str, str] = {}  # key -> "done" | "skipped" | "failed"
    details: dict[str, str] = {}  # key -> detail text

    nginx_sub = "production"

    # Nginx is only relevant for production — omit the step entirely in dev.
    active_steps = [
        step
        for step in WIZARD_STEPS
        if not (step[0] == "nginx" and environment == "development")
    ]
    step_idx = {key: i for i, (key, _) in enumerate(active_steps)}

    prev_failed = False

    # Show initial progress with all steps pending
    _clear_and_show_progress(project_name, steps, details, active_steps, environment)

    # --- Step: Environment ---
    _clear_and_show_progress(
        project_name,
        steps,
        details,
        active_steps,
        environment=environment,
        current_index=step_idx["env"],
        pause=prev_failed,
    )
    console.print(f"  Generate [bold]{environment}[/bold] .env configuration\n")
    if Confirm.ask(
        f"  Run [cyan]phoxtail env create {environment}[/cyan]?", default=True
    ):
        if _run_step(target_dir, ["env", "create", environment]):
            steps["env"] = "done"
            prev_failed = False
        else:
            steps["env"] = "failed"
            details["env"] = "command failed"
            prev_failed = True
    else:
        steps["env"] = "skipped"
        prev_failed = False

    # --- Step: Dockerfile ---
    _clear_and_show_progress(
        project_name,
        steps,
        details,
        active_steps,
        environment=environment,
        current_index=step_idx["dockerfile"],
        pause=prev_failed,
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

    # --- Step: Docker Compose ---
    _clear_and_show_progress(
        project_name,
        steps,
        details,
        active_steps,
        environment=environment,
        current_index=step_idx["compose"],
        pause=prev_failed,
    )
    console.print(f"  Generate [bold]{environment}[/bold] docker-compose.yaml\n")
    if Confirm.ask(
        f"  Run [cyan]phoxtail docker create compose {environment}[/cyan]?",
        default=True,
    ):
        if _run_step(target_dir, ["docker", "create", "compose", environment]):
            steps["compose"] = "done"
            prev_failed = False
        else:
            steps["compose"] = "failed"
            details["compose"] = "command failed"
            prev_failed = True
    else:
        steps["compose"] = "skipped"
        prev_failed = False

    # --- Step: Nginx (production only) ---
    if environment == "production":
        _clear_and_show_progress(
            project_name,
            steps,
            details,
            active_steps,
            environment=environment,
            current_index=step_idx["nginx"],
            pause=prev_failed,
        )
        console.print(f"  Generate [bold]{nginx_sub}[/bold] nginx.conf\n")
        if Confirm.ask(
            f"  Run [cyan]phoxtail nginx create {nginx_sub}[/cyan]?", default=True
        ):
            if _run_step(target_dir, ["nginx", "create", nginx_sub]):
                steps["nginx"] = "done"
                prev_failed = False
            else:
                steps["nginx"] = "failed"
                details["nginx"] = "command failed"
                prev_failed = True
        else:
            steps["nginx"] = "skipped"
            prev_failed = False

    # --- Step: Migrate Database ---
    _clear_and_show_progress(
        project_name,
        steps,
        details,
        active_steps,
        environment=environment,
        current_index=step_idx["migrate"],
        pause=prev_failed,
    )
    console.print("  Apply database migrations\n")
    if Confirm.ask("  Run [cyan]phoxtail manage migrate[/cyan]?", default=True):
        if _run_step(target_dir, ["manage", "migrate"]):
            steps["migrate"] = "done"
            prev_failed = False
        else:
            steps["migrate"] = "failed"
            details["migrate"] = "command failed"
            prev_failed = True
    else:
        steps["migrate"] = "skipped"
        prev_failed = False

    # --- Step: Stream Engine ---
    _clear_and_show_progress(
        project_name,
        steps,
        details,
        active_steps,
        environment=environment,
        current_index=step_idx["stream_engine"],
        pause=prev_failed,
    )
    console.print("  Populate design tokens and stream blocks\n")
    if Confirm.ask("  Run [cyan]Stream Engine[/cyan]?", default=True):
        if not _ensure_migrated(target_dir, steps, details):
            steps["stream_engine"] = "failed"
            details["stream_engine"] = "migration required"
            prev_failed = True
        else:
            # Run populate_design first (streams depend on design tokens)
            console.print()
            console.print("  [bold]Populating design tokens…[/bold]")
            design_ok = _run_step(target_dir, ["manage", "populate_design"])
            if design_ok:
                console.print("  [bold]Populating stream blocks…[/bold]")
                streams_ok = _run_step(target_dir, ["manage", "populate_streams"])
            else:
                streams_ok = False

            if design_ok and streams_ok:
                steps["stream_engine"] = "done"
                prev_failed = False
            else:
                steps["stream_engine"] = "failed"
                if not design_ok:
                    details["stream_engine"] = "populate_design failed"
                else:
                    details["stream_engine"] = "populate_streams failed"
                prev_failed = True
    else:
        steps["stream_engine"] = "skipped"
        prev_failed = False

    # --- Step: Create Superuser ---
    _clear_and_show_progress(
        project_name,
        steps,
        details,
        active_steps,
        environment=environment,
        current_index=step_idx["superuser"],
        pause=prev_failed,
    )
    console.print("  Create an admin superuser account\n")
    if Confirm.ask("  Run [cyan]phoxtail manage createsuperuser[/cyan]?", default=True):
        if not _ensure_migrated(target_dir, steps, details):
            steps["superuser"] = "failed"
            details["superuser"] = "migration required"
            prev_failed = True
        else:
            console.print()
            if _run_step(target_dir, ["manage", "createsuperuser"]):
                # Verify the superuser's email in allauth automatically
                _run_step(target_dir, ["manage", "verify_email", "--all-superusers"])
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
            env=docker_env(),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    else:
        steps["superuser"] = "skipped"
        prev_failed = False

    # --- Step: Launch App ---
    _clear_and_show_progress(
        project_name,
        steps,
        details,
        active_steps,
        environment=environment,
        current_index=step_idx["docker_up"],
        pause=prev_failed,
    )
    console.print("  Build images and start the application\n")
    if Confirm.ask("  Launch the app?", default=True):
        args = ["docker", "up", "--build", "--no-detach"]
        if _run_step(target_dir, args):
            steps["docker_up"] = "done"
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
        project_name, steps, details, active_steps, environment, pause=prev_failed
    )

    return steps


def hatch(
    project_name: str = typer.Argument(
        ...,
        help="Name for the new project (must be a valid Python identifier)",
    ),
    directory: str = typer.Argument(
        None,
        help="Optional destination directory (e.g. '.' for current dir)",
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
        phoxtail hatch myproject .
        phoxtail hatch myproject /tmp/myproject
        phoxtail hatch myproject --no-wizard
    """
    # Validate project name
    error = validate_project_name(project_name)
    if error:
        console.print(f"[red]Error:[/red] {error}")
        raise typer.Exit(1)

    if directory is not None:
        target_dir = Path(directory).expanduser().resolve()
    else:
        target_dir = (Path(".") / project_name).resolve()

    # When an explicit directory is given, scaffold into it (like Django's
    # startproject <name> <directory>). When omitted, create a new folder.
    if directory is None and target_dir.exists():
        if not Confirm.ask(
            f"[yellow]Warning:[/yellow] '{target_dir}' already exists. Overwrite?",
            default=False,
        ):
            console.print("[dim]Cancelled.[/dim]")
            raise typer.Exit(0)
        shutil.rmtree(target_dir)

    try:
        console.print()

        # Ask for environment and optional apps before scaffolding so they are
        # baked into the generated settings — no fragile post-processing needed.
        environment: str | None = None
        if not no_wizard:
            environment = questionary.select(
                "Select environment type:",
                choices=["development", "production"],
            ).ask()
            if environment is None:
                console.print("[dim]Cancelled.[/dim]")
                raise typer.Exit(0)
            console.print()

        selected_apps: list[str] = []
        if not no_wizard and OPTIONAL_APPS:
            choices = [
                questionary.Choice(
                    title=app["name"],
                    value=app["value"],
                )
                for app in OPTIONAL_APPS
            ]
            selected_apps = (
                questionary.checkbox(
                    "Select optional apps to enable:",
                    choices=choices,
                ).ask()
                or []
            )
            if selected_apps:
                names = ", ".join(
                    a["name"] for a in OPTIONAL_APPS if a["value"] in selected_apps
                )
                console.print(f"  [green]Enabled:[/green] {names}")
                console.print()

        # Create project directory and pre-create directories that Docker
        # would otherwise auto-create as root when bind-mounting volumes.
        target_dir.mkdir(parents=True, exist_ok=True)
        (target_dir / "db-backups").mkdir(exist_ok=True)
        (target_dir / "media").mkdir(exist_ok=True)

        # Copy template files with placeholder replacement
        with console.status(f"[bold cyan]Scaffolding '{project_name}'...[/bold cyan]"):
            file_count = _copy_template(project_name, target_dir, selected_apps)

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
                f"at [bold]{target_dir}[/bold]" + req_note,
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
                wizard_steps = _run_wizard(project_name, target_dir, environment)

        # Build context-aware next steps — separate skipped from failed
        next_steps = []
        failed_steps = []

        def _check(
            key: str,
            cmd: str,
            note: str = "",
        ) -> None:
            status = wizard_steps.get(key)
            hint = f"\n    [dim]{note}[/dim]" if note else ""
            if status == "failed":
                failed_steps.append(f"  • [cyan]{cmd}[/cyan]{hint}")
            elif status != "done":
                next_steps.append(f"  • [cyan]{cmd}[/cyan]{hint}")

        _check("env", "phoxtail env create", "generate .env configuration")
        _check("dockerfile", "phoxtail docker create dockerfile", "generate Dockerfile")
        _check(
            "compose", "phoxtail docker create compose", "generate docker-compose.yaml"
        )
        if environment != "development":
            _check(
                "nginx",
                "phoxtail nginx create production",
                "generate nginx.conf",
            )
        _check(
            "migrate",
            "phoxtail manage migrate",
            "apply database migrations",
        )
        _check(
            "stream_engine",
            "phoxtail manage populate_design && phoxtail manage populate_streams",
            "populate design tokens and stream blocks",
        )
        _check(
            "superuser",
            "phoxtail manage createsuperuser",
            "create an admin superuser account",
        )
        _check(
            "docker_up",
            "phoxtail docker up --build",
            "build images and start the application",
        )

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
