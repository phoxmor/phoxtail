"""phoxtail upgrade — pull the latest version of an installed phoxtail package."""

import os
import re
import subprocess
import tomllib
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm

from phoxtail.cli.install import _step_line
from phoxtail.cli.utils.pyproject_sync import apply_diffs, collect_diffs, load_template_doc

console = Console()

UPGRADE_STEPS = [
    ("check", "Check"),
    ("lock", "Lock"),
    ("sync", "Sync"),
    ("build", "Build"),
    ("migrate", "Migrate"),
    ("launch", "Launch"),
]


def _redraw(package: str, steps: dict, details: dict, current_index: int | None = None) -> None:
    console.clear()
    console.print()
    lines = []
    for i, (key, label) in enumerate(UPGRADE_STEPS):
        if key in steps:
            status = steps[key]
        elif current_index is not None and i == current_index:
            status = "current"
        else:
            status = "pending"
        lines.append(_step_line(i, label, status, details.get(key, "")))
    console.print(
        Panel(
            "\n".join(lines),
            title=f"[bold cyan]Upgrading '{package}'[/bold cyan]",
            border_style="cyan",
            expand=False,
        )
    )
    console.print()


def _package_present(content: str, package: str) -> bool:
    # Match "package" or "package[extras]" — extras like [dev] must not fool the check.
    return bool(re.search(rf'"{re.escape(package)}(?:\[|")', content))


def _reconcile_pyproject(pyproject_path: Path) -> str | None:
    """Offer to bring phoxtail's own declarations in pyproject.toml up to date.

    Only meaningful when upgrading phoxtail itself — other installed packages
    don't have a project_template to compare against. Runs before the lock
    step, so it compares against the template shipped with the
    currently-installed phoxtail, one version behind the upgrade in flight;
    any drift the incoming version itself introduces surfaces on the next
    run instead. Returns the original file contents if a change was written,
    so the caller can restore it if a later step fails; returns None
    otherwise.
    """
    original_text = pyproject_path.read_text()
    project_doc = tomllib.loads(original_text)
    template_doc = load_template_doc()
    diffs = collect_diffs(project_doc, template_doc)
    if not diffs:
        return None

    console.print(
        Panel(
            "pyproject.toml has drifted from the current phoxtail template:",
            title="[yellow]Declarations out of date[/yellow]",
            border_style="yellow",
            expand=False,
        )
    )
    for path, diff in diffs.items():
        if path == "project.dependencies":
            old_entry, new_entry = diff
            console.print(f"  [red]- {old_entry}[/red]")
            console.print(f"  [green]+ {new_entry}[/green]")
        else:
            to_remove, to_add = diff
            for entry in to_remove:
                console.print(f"  [red]- {entry}[/red]  (in [{path}])")
            for entry in to_add:
                console.print(f"  [green]+ {entry}[/green]  (in [{path}])")
    console.print()

    # default=False: the tool cannot tell "drifted behind the template" apart
    # from "deliberately dropped this extra" — Enter must never be the one
    # that overwrites a deliberate choice.
    if not Confirm.ask("Apply these changes to pyproject.toml?", default=False):
        console.print("[dim]Skipped — pyproject.toml left unchanged.[/dim]")
        return None

    new_text = apply_diffs(original_text, diffs)
    remaining = collect_diffs(tomllib.loads(new_text), template_doc)
    if remaining:
        console.print(
            Panel(
                "Could not apply automatically — the affected line(s) don't match the "
                "expected formatting. Edit pyproject.toml by hand for:\n"
                + "\n".join(f"  [{path}]" for path in remaining),
                title="[red]Manual edit needed[/red]",
                border_style="red",
                expand=False,
            )
        )
        return None

    pyproject_path.write_text(new_text)
    return original_text


def upgrade(
    package: str = typer.Argument(..., help="Package name to upgrade, e.g. phoxtail-registry"),
    no_build: bool = typer.Option(False, "--no-build", help="Skip the rebuild and launch step"),
) -> None:
    """Upgrade an already-installed package to its latest version.

    Advances the lockfile to the latest commit, syncs .venv, rebuilds the
    Docker image, runs migrations, and restarts the stack. Does not touch
    docker-compose.yaml — run 'phoxtail docker compose' manually if the new
    version added compose services.

        phoxtail upgrade phoxtail-registry
        phoxtail upgrade phoxtail --no-build
    """
    steps: dict[str, str] = {}
    details: dict[str, str] = {}

    step_idx = {key: i for i, (key, _) in enumerate(UPGRADE_STEPS)}

    try:
        # --- Check ---
        _redraw(package, steps, details, step_idx["check"])
        pyproject_path = Path("pyproject.toml")
        if not pyproject_path.exists():
            steps["check"] = "failed"
            _redraw(package, steps, details)
            console.print("[red]Error:[/red] pyproject.toml not found. Run from the project root.")
            raise typer.Exit(1)
        if not _package_present(pyproject_path.read_text(), package):
            steps["check"] = "failed"
            _redraw(package, steps, details)
            console.print(
                Panel(
                    f"[bold]{package}[/bold] is not listed in pyproject.toml.\n"
                    f"Install it first:  [cyan]phoxtail install {package}[/cyan]",
                    title="[red]Not installed[/red]",
                    border_style="red",
                    expand=False,
                )
            )
            raise typer.Exit(1)
        steps["check"] = "done"

        pre_reconcile_text = None
        if package == "phoxtail":
            pre_reconcile_text = _reconcile_pyproject(pyproject_path)
            if pre_reconcile_text is not None:
                details["check"] = "pyproject.toml updated"

        # --- Lock ---
        _redraw(package, steps, details, step_idx["lock"])
        with console.status("  [dim]resolving dependencies...[/dim]"):
            result = subprocess.run(["uv", "lock", "--upgrade-package", package], capture_output=True, text=True)
        if result.returncode != 0:
            if pre_reconcile_text is not None:
                pyproject_path.write_text(pre_reconcile_text)
                details["check"] = "pyproject.toml reverted"
            steps["lock"] = "failed"
            _redraw(package, steps, details)
            console.print(f"[red]uv lock failed:[/red]\n{result.stderr}")
            raise typer.Exit(1)
        steps["lock"] = "done"

        # --- Sync ---
        _redraw(package, steps, details, step_idx["sync"])
        with console.status("  [dim]syncing .venv...[/dim]"):
            result = subprocess.run(["uv", "sync"], capture_output=True, text=True)
        if result.returncode != 0:
            steps["sync"] = "failed"
            _redraw(package, steps, details)
            console.print(f"[red]uv sync failed:[/red]\n{result.stderr}")
            raise typer.Exit(1)
        steps["sync"] = "done"

        # --- Build ---
        # Forward SSH socket so uv sync --frozen can reach private git dependencies.
        _redraw(package, steps, details, step_idx["build"])
        if no_build:
            steps["build"] = "skipped"
            details["build"] = "--no-build"
        else:
            build_cmd = ["docker", "compose", "build"]
            ssh_sock = os.environ.get("SSH_AUTH_SOCK")
            if ssh_sock:
                build_cmd += ["--ssh", f"default={ssh_sock}"]
            rc = subprocess.call(build_cmd)
            if rc != 0:
                steps["build"] = "failed"
                _redraw(package, steps, details)
                raise typer.Exit(1)
            steps["build"] = "done"

        # --- Migrate ---
        if steps.get("build") == "skipped":
            steps["migrate"] = "skipped"
            details["migrate"] = "rebuild required"
        else:
            _redraw(package, steps, details, step_idx["migrate"])
            rc = subprocess.call(
                ["docker", "compose", "run", "--rm", "-T", "web", "python", "manage.py", "migrate"],
            )
            if rc != 0:
                steps["migrate"] = "failed"
                _redraw(package, steps, details)
                raise typer.Exit(1)
            steps["migrate"] = "done"

        # --- Launch ---
        _redraw(package, steps, details, step_idx["launch"])
        if no_build:
            steps["launch"] = "skipped"
        else:
            rc = subprocess.call(["docker", "compose", "up", "-d"])
            if rc == 0:
                steps["launch"] = "done"
            else:
                steps["launch"] = "failed"

        _redraw(package, steps, details)

        failed = [k for k, v in steps.items() if v == "failed"]
        if not failed:
            if steps.get("launch") == "skipped":
                console.print(
                    Panel(
                        f"[green]{package} upgraded.[/green]\n\n"
                        "Run [cyan]phoxtail docker up --build[/cyan] to rebuild your containers.",
                        border_style="green",
                        expand=False,
                    )
                )
        else:
            console.print(
                Panel(
                    f"[yellow]{package} upgrade completed with warnings.[/yellow]\n\nFailed steps: "
                    + ", ".join(failed),
                    border_style="yellow",
                    expand=False,
                )
            )

    except typer.Exit:
        raise
    except KeyboardInterrupt:
        console.print("\n[dim]Cancelled.[/dim]")
        raise typer.Exit(0)
