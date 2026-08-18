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

from phoxtail import __version__
from phoxtail.cli.utils.config import validate_project_name
from phoxtail.cli.utils.docker import docker_env
from phoxtail.cli.utils.net import net_stack_running

console = Console()

PLACEHOLDER = "{{ phoxtail_project_name }}"
# Scaffolded projects pin the phoxtail that made them, so a release that
# breaks them can never reach them unattended.
VERSION_PLACEHOLDER = "{{ phoxtail_version }}"
# Stable sentinel that survives hatch — phoxtail install inserts above this line.
INSTALL_MARKER = "    # phoxtail:apps\n"
# Sentinel used in template directory and file names that should be renamed
# to the user's project name at scaffold time (e.g. the user app directory
# and its Django template namespace).
DIR_SENTINEL = "__project_name__"
TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "project_template"

# Wizard step definitions: (key, label)
WIZARD_STEPS = [
    ("configure", "Config"),
    ("attach_net", "Network"),
    ("setup_db", "Database"),
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
        title=(f"[bold cyan]Hatching '{project_name}'[/bold cyan] [dim]{environment}[/dim]"),
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
        console.input("[dim]Press Enter to move on (retry later)...[/dim]")
    console.clear()
    console.print()
    console.print(_render_progress(project_name, steps, details, wizard_steps, environment, current_index))
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

        rel_parts = tuple(project_name if part == DIR_SENTINEL else part for part in rel_path.parts)
        dest_path = target_dir.joinpath(*rel_parts)
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            content = src_path.read_text(encoding="utf-8")
            if PLACEHOLDER in content:
                content = content.replace(PLACEHOLDER, project_name)
            if VERSION_PLACEHOLDER in content:
                content = content.replace(VERSION_PLACEHOLDER, __version__)
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


def _run_wizard(project_name: str, target_dir: Path, environment: str) -> dict[str, str]:
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
                compose_ok = _run_step(target_dir, ["docker", "create", "compose", environment])

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

    # --- Step: Attach to shared net ---
    # Placed before the database and launch steps, both of which shell out to
    # `docker compose run`/`up`: attaching rewrites COMPOSE_FILE in .env, so
    # doing it first means every later step already runs against the network
    # the user chose, instead of moving it out from under a running project.
    #
    # Requires the config step's output. `net attach` edits .env and appends
    # docker-compose.yaml to COMPOSE_FILE, creating .env if absent — so on a
    # skipped config it would write a COMPOSE_FILE naming a base file that
    # does not exist, breaking every later `docker compose` call, and the
    # `phoxtail env create` we then tell the user to run would overwrite that
    # .env and silently strip the wiring back out while the members file
    # still claims the project is attached.
    configured = (target_dir / ".env").exists() and (target_dir / "docker-compose.yaml").exists()

    _clear_and_show_progress(
        project_name,
        steps,
        details,
        active_steps,
        environment=environment,
        current_index=step_idx["attach_net"],
        pause=prev_failed,
    )
    if not configured:
        steps["attach_net"] = "skipped"
        prev_failed = False
    elif Confirm.ask(
        "  Attach to the shared local net (reachable at http://<project>.localhost alongside other Phoxtail projects)?",
        default=False,
    ):
        details["attach_net"] = "attaching…"
        _clear_and_show_progress(
            project_name,
            steps,
            details,
            active_steps,
            environment=environment,
            current_index=step_idx["attach_net"],
        )
        attach_ok = _run_step(target_dir, ["net", "attach"])

        if not attach_ok:
            steps["attach_net"] = "failed"
            details["attach_net"] = "net attach failed"
            prev_failed = True
        else:
            steps["attach_net"] = "done"
            prev_failed = False
    else:
        steps["attach_net"] = "skipped"
        prev_failed = False

    # Clear the transient "attaching…" text, then restate the one detail worth
    # carrying into the final panel — a skip the user never got asked about.
    details.pop("attach_net", None)
    if not configured:
        details["attach_net"] = "needs project configuration first"

    # --- Step: Database ---
    _clear_and_show_progress(
        project_name,
        steps,
        details,
        active_steps,
        environment=environment,
        current_index=step_idx["setup_db"],
        pause=prev_failed,
    )

    if Confirm.ask("  Set up the database?", default=True):
        details["setup_db"] = "initializing…"
        _clear_and_show_progress(
            project_name,
            steps,
            details,
            active_steps,
            environment=environment,
            current_index=step_idx["setup_db"],
        )
        migrate_ok = _run_step(target_dir, ["manage", "migrate"])

        if not migrate_ok:
            steps["setup_db"] = "failed"
            details["setup_db"] = "migrate failed"
            prev_failed = True
        else:
            steps["setup_db"] = "done"
            prev_failed = False
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
    if Confirm.ask("  Create an admin account?", default=True):
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
    if Confirm.ask("  Launch the app?", default=True):
        args = ["docker", "up", "--build"]
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
    _clear_and_show_progress(project_name, steps, details, active_steps, environment, pause=prev_failed)

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

        docker_registry: str | None = None
        if not no_wizard and environment == "production":
            raw = questionary.text(
                "Docker registry for production images (e.g. ghcr.io/myorg):",
                instruction="Leave blank to configure later in phoxtail.toml",
            ).ask()
            if raw is None:
                console.print("[dim]Cancelled.[/dim]")
                raise typer.Exit(0)
            docker_registry = raw.strip() or None
            console.print()

        # Create project directory and pre-create directories that Docker
        # would otherwise auto-create as root when bind-mounting volumes.
        target_dir.mkdir(parents=True, exist_ok=True)
        (target_dir / "db-backups").mkdir(exist_ok=True)
        (target_dir / "media").mkdir(exist_ok=True)

        with console.status(f"[bold cyan]Scaffolding '{project_name}'...[/bold cyan]"):
            _copy_template(project_name, target_dir)

            if docker_registry:
                toml_path = target_dir / "phoxtail.toml"
                toml_content = toml_path.read_text(encoding="utf-8")
                toml_content = toml_content.replace(
                    '# registry = "ghcr.io/<org_name>"',
                    f'registry = "{docker_registry}"',
                )
                toml_path.write_text(toml_content, encoding="utf-8")

            # Resolve and lock all dependencies (public from PyPI + phoxtail from git)
            locked = subprocess.run(
                ["uv", "lock"],
                cwd=target_dir,
            )

        # Summary
        lock_note = (
            ""
            if locked.returncode == 0
            else (
                "\n[yellow]⚠[/yellow] uv lock failed — run [cyan]uv lock[/cyan] in the project directory once SSH is available"  # noqa: E501
            )
        )
        console.print(
            Panel(
                f"[green]Project '{project_name}' created[/green] at [bold]{target_dir}[/bold]" + lock_note,
                border_style="green",
                expand=False,
            )
        )
        console.print()

        # Run the setup wizard unless --no-wizard
        wizard_steps: dict[str, str] = {}
        if not no_wizard:
            run_wizard = Confirm.ask("Would you like to run the setup wizard?", default=True)
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
            + (" && phoxtail nginx create production" if environment == "production" else "")
        )
        _check("configure", configure_cmd, "generate project configuration files")
        # Deliberately not a `_check`: the shared net is opt-in, so a declined
        # or not-applicable attach is a choice, not an outstanding task, and
        # listing it would nag every user who does not want it. Only a genuine
        # failure is worth surfacing.
        if wizard_steps.get("attach_net") == "failed":
            failed_steps.append(
                "  • [cyan]phoxtail net attach[/cyan]"
                "\n    [dim]join the shared local net at http://<project>.localhost[/dim]"
            )
        _check(
            "setup_db",
            "phoxtail manage migrate",
            "initialize the database",
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

        # `net attach` creates the shared network but does not start Traefik —
        # only `net up` does. Without this the project is attached, running,
        # and unreachable at the hostname the attach step just promised.
        if wizard_steps.get("attach_net") == "done" and not net_stack_running():
            next_steps.append(
                "  • [cyan]phoxtail net up[/cyan]"
                "\n    [dim]start the shared net's router so http://<project>.localhost resolves[/dim]"
            )

        # Assemble next steps
        all_steps = [f"  • [cyan]cd {target_dir}[/cyan]\n    [dim]navigate to the project directory[/dim]"]
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
