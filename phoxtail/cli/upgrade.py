"""phoxtail upgrade — pull the latest version of an installed phoxtail package."""

import os
import subprocess
import tomllib
from pathlib import Path

import typer
from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.prompt import Confirm

from phoxtail.cli.install import _step_line
from phoxtail.cli.utils.packages import (
    declared_requirement,
    entry_versions,
    has_git_source,
    locked_entries,
)
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
    # escape(): entries like phoxtail[dev] read as Rich markup tags and
    # vanish from the output otherwise.
    for path, diff in diffs.items():
        if path == "project.dependencies":
            old_entry, new_entry = diff
            console.print(f"  [red]- {escape(old_entry)}[/red]")
            console.print(f"  [green]+ {escape(new_entry)}[/green]")
        else:
            to_remove, to_add = diff
            for entry in to_remove:
                console.print(f"  [red]- {escape(entry)}[/red]  (in {escape(f'[{path}]')})")
            for entry in to_add:
                console.print(f"  [green]+ {escape(entry)}[/green]  (in {escape(f'[{path}]')})")
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
                + "\n".join(f"  {escape(f'[{path}]')}" for path in remaining),
                title="[red]Manual edit needed[/red]",
                border_style="red",
                expand=False,
            )
        )
        return None

    pyproject_path.write_text(new_text)
    return original_text


def _report_unmoved(package: str, entries: list[dict], requirement: str | None) -> None:
    """Explain why an upgrade resolved to the same thing, and where the ceiling lives."""
    at = f"[bold]{package} {', '.join(entry_versions(entries))}[/bold]"
    if has_git_source(entries):
        body = f"{at} is already at the latest commit on the branch it tracks."
    elif requirement is not None and not any(ch in requirement for ch in "<>=~!"):
        # An unpinned declaration has nothing to widen; the ceiling, if any,
        # belongs to some other package's constraint.
        body = f"{at} is already the newest version the resolver can reach."
    elif requirement is None:
        body = (
            f"{at} is already the newest version allowed by the packages that require it.\n"
            f"{package} is not declared in pyproject.toml — it comes in transitively, so its\n"
            "ceiling moves only when the package that pins it does:\n"
            "  [cyan]phoxtail upgrade phoxtail[/cyan]"
        )
    else:
        body = (
            f"{at} is already the newest version allowed by your own constraint:\n"
            f'  [dim]"{escape(requirement)}"[/dim]  (in pyproject.toml)\n'
            "Widen it there to go further."
        )
    console.print(Panel(body, title="[yellow]Nothing to upgrade[/yellow]", border_style="yellow", expand=False))


def upgrade(
    package: str = typer.Argument(..., help="Package name to upgrade, e.g. wagtail"),
    no_build: bool = typer.Option(False, "--no-build", help="Skip the rebuild and launch step"),
) -> None:
    """Upgrade a package in this project's dependency graph to its latest version.

    Works for anything uv.lock resolves — a phoxtail package, a library the
    project declares itself, or one pulled in transitively. Advances the
    lockfile, syncs .venv, rebuilds the Docker image, runs migrations, and
    restarts the stack. Does not touch docker-compose.yaml — run
    'phoxtail docker compose' manually if the new version added compose
    services.

        phoxtail upgrade phoxtail-registry
        phoxtail upgrade wagtail
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
        lock_path = Path("uv.lock")
        # uv.lock is the authority: it resolves transitive packages too, and
        # those are exactly what `uv lock --upgrade-package` can move. Fall
        # back to the declarations when a project has not been locked yet.
        lock_before = lock_path.read_text() if lock_path.exists() else None
        try:
            entries_before = locked_entries(lock_before, package) if lock_before is not None else []
            requirement = declared_requirement(pyproject_path.read_text(), package)
        except tomllib.TOMLDecodeError as exc:
            steps["check"] = "failed"
            _redraw(package, steps, details)
            console.print(f"[red]Could not parse the project's TOML:[/red] {exc}")
            raise typer.Exit(1) from exc
        if not entries_before and requirement is None:
            steps["check"] = "failed"
            _redraw(package, steps, details)
            console.print(
                Panel(
                    f"[bold]{package}[/bold] is not part of this project's dependencies.\n"
                    f"Install it first:  [cyan]phoxtail install {package}[/cyan]",
                    title="[red]Not installed[/red]",
                    border_style="red",
                    expand=False,
                )
            )
            raise typer.Exit(1)
        steps["check"] = "done"
        if requirement is None:
            details["check"] = "transitive dependency"

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

        # `uv lock` exits 0 whether or not anything moved. Upgrading past a
        # constraint set elsewhere is impossible, so say that instead of
        # rebuilding and restarting the stack for an unchanged image.
        lock_after = lock_path.read_text() if lock_path.exists() else None
        entries_after = locked_entries(lock_after, package) if lock_after is not None else []
        # The whole file, not just this package: `uv lock` re-resolves the
        # entire graph, so it can leave `package` where it was while moving
        # something else. Skipping the sync then strands .venv and the image
        # behind a lockfile that did change.
        if pre_reconcile_text is None and entries_before and lock_after == lock_before:
            steps["lock"] = "skipped"
            details["lock"] = "nothing to resolve"
            # An unchanged lockfile can still be ahead of .venv (a pulled
            # uv.lock, say), so sync before stopping — cheap when they
            # already agree. The Docker image stays as it is: rebuilding
            # belongs to the deploy flow, not to a no-op upgrade.
            result = subprocess.run(["uv", "sync"], capture_output=True, text=True)
            steps["sync"] = "done" if result.returncode == 0 else "failed"
            _redraw(package, steps, details)
            _report_unmoved(package, entries_before, requirement)
            raise typer.Exit(0 if result.returncode == 0 else 1)
        steps["lock"] = "done"
        if entries_after:
            was, now = ", ".join(entry_versions(entries_before)), ", ".join(entry_versions(entries_after))
            details["lock"] = f"{was} → {now}" if was and was != now else now

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
