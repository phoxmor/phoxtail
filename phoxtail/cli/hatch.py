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
from phoxtail.core.wiring import find_phoxtail_config

console = Console()

PLACEHOLDER = "{{ phoxtail_project_name }}"
APPS_MARKER = "    # {{ phoxtail_optional_apps }}\n"
# Sentinel used in template directory and file names that should be renamed
# to the user's project name at scaffold time (e.g. the user app directory
# and its Django template namespace).
DIR_SENTINEL = "__project_name__"
TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "project_template"

# Files that are only copied into a hatched project when a predicate holds.
# The predicate receives the list of selected optional-app dotted names.
CONDITIONAL_FILES: dict[str, callable] = {
    "src/celery.py": lambda apps: any(
        _get_app_info(app)["requires_celery"] for app in apps
    ),
}

# Optional phoxtail apps available during hatching.
OPTIONAL_APPS = [
    {"name": "Blog", "value": "phoxtail.blog"},
    {"name": "Dashboard", "value": "phoxtail.dashboard"},
    {"name": "Booking", "value": "phoxtail.booking"},
]


def _get_app_info(dotted_app: str) -> dict:
    """Read celery + requirements metadata from an optional app's PhoxtailAppConfig.

    Apps that don't ship a PhoxtailAppConfig (e.g. plain-AppConfig apps like
    blog) return empty defaults.
    """
    config = find_phoxtail_config(dotted_app)
    if config is None:
        return {"requires_celery": False, "requirements": []}
    return {
        "requires_celery": config.requires_celery,
        "requirements": list(config.requirements),
    }


def _collect_extra_requirements(selected_apps: list[str]) -> list[str]:
    """Collect deduplicated extra requirements from selected optional apps."""
    extras: list[str] = []
    for app in selected_apps:
        for req in _get_app_info(app)["requirements"]:
            if req not in extras:
                extras.append(req)
    return extras


# Wizard step definitions: (key, label)
WIZARD_STEPS = [
    ("configure", "Configure"),
    ("setup_db", "Populate"),
    ("superuser", "Access"),
    ("docker_up", "Launch"),
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
    INSTALLED_APPS (replacing the ``APPS_MARKER`` line). Per-app
    integration (context processors, URL mounts, celery settings,
    dependencies) is handled at runtime by ``phoxtail.core.wiring`` via
    each app's ``PhoxtailAppConfig``.

    Returns the number of files copied.
    """
    if not TEMPLATE_DIR.is_dir():
        raise FileNotFoundError(
            f"Template directory not found at: {TEMPLATE_DIR}\n"
            "The hatch command requires phoxtail[engine] or an editable "
            "install of the full repository."
        )

    selected = optional_apps or []

    if selected:
        apps_replacement = "".join(f'    "{app}",\n' for app in selected)
    else:
        apps_replacement = ""

    # Evaluate which conditional files should be skipped for this project.
    skipped_rel_paths = {
        rel for rel, predicate in CONDITIONAL_FILES.items() if not predicate(selected)
    }

    file_count = 0
    for src_path in sorted(TEMPLATE_DIR.rglob("*")):
        if src_path.is_dir():
            continue

        rel_path = src_path.relative_to(TEMPLATE_DIR)
        if rel_path.as_posix() in skipped_rel_paths:
            continue

        # Rename sentinel path components (e.g. __project_name__/) to the
        # concrete project name — both for directories and file names.
        rel_parts = tuple(
            project_name if part == DIR_SENTINEL else part for part in rel_path.parts
        )
        dest_path = target_dir.joinpath(*rel_parts)
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        # Try text replacement; fall back to binary copy for non-text files
        try:
            content = src_path.read_text(encoding="utf-8")
            if PLACEHOLDER in content:
                content = content.replace(PLACEHOLDER, project_name)
            if APPS_MARKER in content:
                content = content.replace(APPS_MARKER, apps_replacement)
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

    active_steps = list(WIZARD_STEPS)
    step_idx = {key: i for i, (key, _) in enumerate(active_steps)}

    prev_failed = False

    # Show initial progress with all steps pending
    _clear_and_show_progress(project_name, steps, details, active_steps, environment)

    # --- Step: Configure Project ---
    # Generates all configuration files: .env, Dockerfile, docker-compose.yaml,
    # and (production only) nginx.conf. None of these touch a container or
    # database — they are purely file-generation operations that belong together.
    _clear_and_show_progress(
        project_name,
        steps,
        details,
        active_steps,
        environment=environment,
        current_index=step_idx["configure"],
        pause=prev_failed,
    )
    console.print(
        f"  Generate [bold]{environment}[/bold] configuration files"
        + (
            " (.env, Dockerfile, docker-compose.yaml, nginx.conf)"
            if environment == "production"
            else " (.env, Dockerfile, docker-compose.yaml)"
        )
        + "\n"
    )

    def _redraw(detail: str = "") -> None:
        """Clear and redraw the progress panel, updating the current step detail."""
        if detail:
            details["configure"] = detail
        _clear_and_show_progress(
            project_name,
            steps,
            details,
            active_steps,
            environment=environment,
            current_index=step_idx["configure"],
        )

    if Confirm.ask("  Generate project configuration?", default=True):
        _redraw("generating .env…")
        env_ok = _run_step(target_dir, ["env", "create", environment])

        if not env_ok:
            steps["configure"] = "failed"
            details["configure"] = "env create failed"
            prev_failed = True
        else:
            _redraw("generating Dockerfile…")
            dockerfile_ok = _run_step(target_dir, ["docker", "create", "dockerfile"])

            if not dockerfile_ok:
                steps["configure"] = "failed"
                details["configure"] = "dockerfile failed"
                prev_failed = True
            else:
                _redraw("generating docker-compose.yaml…")
                compose_ok = _run_step(
                    target_dir, ["docker", "create", "compose", environment]
                )

                if not compose_ok:
                    steps["configure"] = "failed"
                    details["configure"] = "docker compose failed"
                    prev_failed = True
                elif environment == "production":
                    _redraw("generating nginx.conf…")
                    nginx_ok = _run_step(target_dir, ["nginx", "create", nginx_sub])

                    if nginx_ok:
                        steps["configure"] = "done"
                        prev_failed = False
                    else:
                        steps["configure"] = "failed"
                        details["configure"] = "nginx failed"
                        prev_failed = True
                else:
                    steps["configure"] = "done"
                    prev_failed = False
    else:
        steps["configure"] = "skipped"
        prev_failed = False

    # Clear sub-step detail so the panel is clean when the next step renders.
    details.pop("configure", None)

    # --- Step: Create Database ---
    # Runs four operations in sequence: migrate → populate_design →
    # populate_streams → bootstrap_site. They are non-negotiable as a unit —
    # each depends on the previous — so they share one user-facing prompt.
    _clear_and_show_progress(
        project_name,
        steps,
        details,
        active_steps,
        environment=environment,
        current_index=step_idx["setup_db"],
        pause=prev_failed,
    )
    console.print(
        "  Run migrations, seed design tokens, populate blocks, and bootstrap the site\n"
    )

    def _redraw_db(detail: str = "") -> None:
        """Clear and redraw the progress panel for the database step."""
        if detail:
            details["setup_db"] = detail
        _clear_and_show_progress(
            project_name,
            steps,
            details,
            active_steps,
            environment=environment,
            current_index=step_idx["setup_db"],
        )

    if Confirm.ask("  Set up the database?", default=True):
        _redraw_db("running migrations…")
        migrate_ok = _run_step(target_dir, ["manage", "migrate"])

        if not migrate_ok:
            steps["setup_db"] = "failed"
            details["setup_db"] = "migrate failed"
            prev_failed = True
        else:
            _redraw_db("populating design tokens…")
            design_ok = _run_step(target_dir, ["manage", "populate_design"])

            if not design_ok:
                steps["setup_db"] = "failed"
                details["setup_db"] = "populate_design failed"
                prev_failed = True
            else:
                _redraw_db("populating stream blocks…")
                streams_ok = _run_step(target_dir, ["manage", "populate_streams"])

                if not streams_ok:
                    steps["setup_db"] = "failed"
                    details["setup_db"] = "populate_streams failed"
                    prev_failed = True
                else:
                    _redraw_db("bootstrapping site…")
                    site_ok = _run_step(
                        target_dir,
                        ["manage", "bootstrap_site", "--app-label", project_name],
                    )

                    if site_ok:
                        steps["setup_db"] = "done"
                        prev_failed = False
                    else:
                        steps["setup_db"] = "failed"
                        details["setup_db"] = "bootstrap_site failed"
                        prev_failed = True
    else:
        steps["setup_db"] = "skipped"
        prev_failed = False

    # Clear sub-step detail so the panel is clean when the next step renders.
    details.pop("setup_db", None)

    # --- Step: Create Admin Account ---
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

            # Write the selected optional apps into phoxtail.toml so that
            # subsequent CLI commands (e.g. docker create compose) can
            # introspect each app's PhoxtailAppConfig without re-asking.
            if selected_apps:
                toml_path = target_dir / "phoxtail.toml"
                apps_toml = "[" + ", ".join(f'"{a}"' for a in selected_apps) + "]"
                content = toml_path.read_text(encoding="utf-8")
                content = content.replace("apps = []", f"apps = {apps_toml}")
                toml_path.write_text(content, encoding="utf-8")

            # Generate requirements.in from template, then append any
            # extra requirements contributed by selected optional apps
            # (e.g. booking brings in celery + django-celery-beat).
            requirements_in = render_template("requirements/requirements.in", {})
            extras = _collect_extra_requirements(selected_apps)
            if extras:
                suffix = "\n# Optional phoxtail apps\n" + "\n".join(extras) + "\n"
                requirements_in = requirements_in.rstrip("\n") + "\n" + suffix
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

        configure_cmd = (
            f"phoxtail env create {environment or 'development'}"
            " && phoxtail docker create dockerfile"
            f" && phoxtail docker create compose {environment or 'development'}"
            + (
                " && phoxtail nginx create production"
                if environment == "production"
                else ""
            )
        )
        _check("configure", configure_cmd, "generate project configuration files")
        _check(
            "setup_db",
            (
                "phoxtail manage migrate"
                " && phoxtail manage populate_design"
                " && phoxtail manage populate_streams"
                f" && phoxtail manage bootstrap_site --app-label {project_name}"
            ),
            "set up the database (migrate, seed tokens/blocks, bootstrap site)",
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
