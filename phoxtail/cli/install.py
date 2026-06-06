"""phoxtail install — manage phoxtail packages in a project."""

import os
import re
import subprocess
import sys
from pathlib import Path

import typer
import yaml
from rich.console import Console
from rich.panel import Panel

from phoxtail.cli.hatch import INSTALL_MARKER
from phoxtail.cli.utils.config import docker_image_slug, get_project_name
from phoxtail.cli.utils.docker import collect_package_compose_fragments
from phoxtail.cli.utils.templates import render_template

console = Console()

INSTALL_STEPS = [
    ("check", "Check"),
    ("lock", "Lock"),
    ("sync", "Sync"),
    ("register", "Register"),
    ("compose", "Compose"),
    ("build", "Build"),
    ("migrate", "Migrate"),
    ("launch", "Launch"),
]

_ICONS = {
    "done": "[green]✓[/green]",
    "failed": "[red]✗[/red]",
    "skipped": "[dim]⏭[/dim]",
    "current": "[bold cyan]▸[/bold cyan]",
    "pending": "[dim]○[/dim]",
}


def _step_line(index: int, label: str, status: str, detail: str = "") -> str:
    icon = _ICONS[status]
    num = f"{index + 1}."
    suffix = f"  [dim]{detail}[/dim]" if detail else ""
    if status == "current":
        return f"  {icon} [bold]{num} {label}[/bold]{suffix}"
    return f"  {icon} {num} {label}{suffix}"


def _render_panel(package: str, steps: dict, details: dict, current_index: int | None = None) -> Panel:
    lines = []
    for i, (key, label) in enumerate(INSTALL_STEPS):
        if key in steps:
            status = steps[key]
        elif current_index is not None and i == current_index:
            status = "current"
        else:
            status = "pending"
        lines.append(_step_line(i, label, status, details.get(key, "")))
    return Panel(
        "\n".join(lines),
        title=f"[bold cyan]Installing '{package}'[/bold cyan]",
        border_style="cyan",
        expand=False,
    )


def _redraw(package: str, steps: dict, details: dict, current_index: int | None = None) -> None:
    console.clear()
    console.print()
    console.print(_render_panel(package, steps, details, current_index))
    console.print()


def _run_phoxtail(*args: str) -> bool:
    result = subprocess.run([sys.executable, "-m", "phoxtail", *args])
    return result.returncode == 0


def _package_name_from_url(url: str) -> str:
    name = url.rstrip("/").split("/")[-1]
    if name.endswith(".git"):
        name = name[:-4]
    return name


def _preflight_pypi(package: str) -> tuple[bool, str]:
    result = subprocess.run(
        ["uv", "pip", "index", "versions", package],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return False, (
            f"[bold]{package}[/bold] was not found on PyPI.\n"
            "If this is a private package, provide its git URL:\n"
            f"  [cyan]phoxtail install --url ssh://git@github.com/org/{package}.git[/cyan]"
        )
    return True, ""


def _preflight_git(url: str, package: str) -> tuple[bool, str]:
    result = subprocess.run(
        ["git", "ls-remote", url, "HEAD"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        stderr_lower = result.stderr.lower()
        if "permission denied" in stderr_lower or "publickey" in stderr_lower:
            return False, (
                f"SSH access denied for [bold]{package}[/bold].\n"
                "You don't have access to this repository — contact [cyan]hello@phoxmor.com[/cyan]."
            )
        return False, f"Could not reach [bold]{url}[/bold].\nError: {result.stderr.strip()}"
    return True, ""


def _add_dependency(content: str, package: str) -> str:
    if f'"{package}"' in content:
        return content
    # The dependencies block in our template is always followed by \n\n[tool.uv].
    marker = "]\n\n[tool.uv]"
    if marker in content:
        return content.replace(marker, f'    "{package}",\n{marker}', 1)
    return content


def _add_uv_source(content: str, package: str, git_url: str, branch: str) -> str:
    if git_url in content:
        return content
    source_line = f'{package} = {{ git = "{git_url}", branch = "{branch}" }}'
    if "[tool.uv.sources]" in content:
        return content.rstrip() + f"\n{source_line}\n"
    return content


def _detect_app_info(package: str) -> tuple[str, str] | tuple[None, None]:
    """Return (apps_entry, django_label) for the installed package, or (None, None).

    apps_entry   — the string that belongs in INSTALLED_APPS (Python module name).
    django_label — the short label Django registers the app under; comes from
                   AppConfig.label in apps.py, falling back to the last dotted
                   segment of AppConfig.name.
    """
    normalized = re.sub(r"[-_.]+", "_", package).lower()
    for site_packages in sorted(Path(".venv").glob("lib/python*/site-packages")):
        candidate = site_packages / normalized
        if not candidate.is_dir():
            continue
        apps_entry = normalized
        django_label = normalized
        apps_py = candidate / "apps.py"
        if apps_py.exists():
            content = apps_py.read_text()
            m = re.search(r'\blabel\s*=\s*["\']([^"\']+)["\']', content)
            if m:
                django_label = m.group(1)
            else:
                m = re.search(r'\bname\s*=\s*["\']([^"\']+)["\']', content)
                if m:
                    django_label = m.group(1).rsplit(".", 1)[-1]
        return apps_entry, django_label
    return None, None


def _detect_postgres_version() -> str:
    compose_path = Path("docker-compose.yaml")
    if compose_path.exists():
        try:
            data = yaml.safe_load(compose_path.read_text())
            image = data.get("services", {}).get("db", {}).get("image", "")
            m = re.match(r"postgres:(\d+)", image)
            if m:
                return m.group(1)
        except Exception:
            pass
    return "18"


def _detect_environment() -> str:
    compose_path = Path("docker-compose.yaml")
    if compose_path.exists():
        try:
            data = yaml.safe_load(compose_path.read_text())
            target = data.get("services", {}).get("web", {}).get("build", {}).get("target", "")
            if target in ("development", "production"):
                return target
        except Exception:
            pass
    return "development"


def _insert_installed_app(settings_path: Path, app_label: str) -> bool:
    content = settings_path.read_text()
    if f'"{app_label}"' in content:
        return False
    if INSTALL_MARKER not in content:
        console.print(
            f"[yellow]Warning:[/yellow] [bold]# phoxtail:apps[/bold] sentinel not found in {settings_path}.\n"
            f'Add [cyan]"{app_label}"[/cyan] to INSTALLED_APPS manually.'
        )
        return False
    settings_path.write_text(content.replace(INSTALL_MARKER, f'    "{app_label}",\n{INSTALL_MARKER}'))
    return True


def _regenerate_compose(project_name: str, postgres_version: str, environment: str) -> None:
    context = {
        "environment": environment,
        "image_name": f"{docker_image_slug(project_name)}/{docker_image_slug(project_name)}:latest",
        "postgres_version": postgres_version,
        "pg_data_path": "/var/lib/postgresql" if int(postgres_version) >= 18 else "/var/lib/postgresql/data",
    }
    base = yaml.safe_load(render_template("docker/docker-compose.yaml", context))
    fragments = collect_package_compose_fragments(context)
    if fragments["services"]:
        base.setdefault("services", {}).update(fragments["services"])
    if fragments["volumes"]:
        base.setdefault("volumes", {}).update(fragments["volumes"])
    Path("docker-compose.yaml").write_text(
        yaml.dump(base, default_flow_style=False, sort_keys=False, allow_unicode=True)
    )


def install(
    package: str | None = typer.Argument(
        None,
        help="Package name for PyPI installs, e.g. django-allauth",
    ),
    url: str | None = typer.Option(
        None,
        "--url",
        help="Git SSH URL — package name is derived from the URL automatically",
    ),
    branch: str = typer.Option("main", "--branch", help="Git branch to track (only used with --url)"),
    no_build: bool = typer.Option(False, "--no-build", help="Skip the rebuild and launch step"),
) -> None:
    """Add a package to this project.

    PyPI install:
        phoxtail install django-allauth

    Private git install (name derived from URL):
        phoxtail install --url ssh://git@github.com/phoxmor/phoxtail-blog.git
        phoxtail install --url ssh://git@github.com/phoxmor/phoxtail-booking.git --no-build

    Updates pyproject.toml, locks dependencies, registers the app in
    INSTALLED_APPS, syncs .venv, and regenerates docker-compose.yaml.
    """
    if url and not package:
        package = _package_name_from_url(url)
    elif not package:
        console.print("[red]Error:[/red] Provide a package name or --url.")
        raise typer.Exit(1)

    project_name = get_project_name()
    postgres_version = _detect_postgres_version()
    environment = _detect_environment()

    steps: dict[str, str] = {}
    details: dict[str, str] = {}

    step_idx = {key: i for i, (key, _) in enumerate(INSTALL_STEPS)}

    try:
        # --- Check ---
        _redraw(package, steps, details, step_idx["check"])
        pyproject_path = Path("pyproject.toml")
        if pyproject_path.exists() and f'"{package}"' in pyproject_path.read_text():
            steps["check"] = "skipped"
            _redraw(package, steps, details)
            console.print(
                Panel(
                    f"[bold]{package}[/bold] is already listed in pyproject.toml.",
                    title="[yellow]Already installed[/yellow]",
                    border_style="yellow",
                    expand=False,
                )
            )
            raise typer.Exit(0)
        with console.status("  [dim]verifying access...[/dim]"):
            if url:
                ok, err = _preflight_git(url, package)
            else:
                ok, err = _preflight_pypi(package)
        if not ok:
            steps["check"] = "failed"
            _redraw(package, steps, details)
            console.print(Panel(err, title="[red]Pre-flight failed[/red]", border_style="red", expand=False))
            raise typer.Exit(1)
        steps["check"] = "done"

        # --- Lock ---
        _redraw(package, steps, details, step_idx["lock"])
        pyproject_path = Path("pyproject.toml")
        if not pyproject_path.exists():
            steps["lock"] = "failed"
            _redraw(package, steps, details)
            console.print("[red]Error:[/red] pyproject.toml not found. Run from the project root.")
            raise typer.Exit(1)
        original_content = pyproject_path.read_text()
        updated_content = _add_dependency(original_content, package)
        if url:
            updated_content = _add_uv_source(updated_content, package, url, branch)
        pyproject_path.write_text(updated_content)

        with console.status("  [dim]resolving dependencies...[/dim]"):
            result = subprocess.run(["uv", "lock", "--upgrade-package", package], capture_output=True, text=True)
        if result.returncode != 0:
            pyproject_path.write_text(original_content)
            steps["lock"] = "failed"
            details["lock"] = "reverted"
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

        # --- Register ---
        _redraw(package, steps, details, step_idx["register"])
        with console.status("  [dim]detecting app label...[/dim]"):
            apps_entry, django_label = _detect_app_info(package)
        if apps_entry is None:
            steps["register"] = "skipped"
            details["register"] = "no app label detected — add manually"
        else:
            settings_path = Path("src/settings/base.py")
            if _insert_installed_app(settings_path, apps_entry):
                steps["register"] = "done"
                details["register"] = apps_entry
            else:
                steps["register"] = "skipped"
                details["register"] = f"{apps_entry} already registered"

        # --- Compose ---
        _redraw(package, steps, details, step_idx["compose"])
        with console.status("  [dim]regenerating docker-compose.yaml...[/dim]"):
            try:
                _regenerate_compose(project_name, postgres_version, environment)
                steps["compose"] = "done"
            except Exception as e:
                steps["compose"] = "failed"
                details["compose"] = str(e)

        # --- Build ---
        # Build before migrate so the container image has the new package.
        # Explicitly forward the SSH socket (same pattern as docker.py) so
        # uv sync --frozen can reach private git dependencies without hanging.
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
        # Image already built above; start detached so the wizard can finish.
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
                        f"[green]{package} installed.[/green]\n\n"
                        "Run [cyan]phoxtail docker up --build[/cyan] to rebuild your containers.",
                        border_style="green",
                        expand=False,
                    )
                )
        else:
            console.print(
                Panel(
                    f"[yellow]{package} installed with warnings.[/yellow]\n\n" + "Failed steps: " + ", ".join(failed),
                    border_style="yellow",
                    expand=False,
                )
            )

    except typer.Exit:
        raise
    except KeyboardInterrupt:
        console.print("\n[dim]Cancelled.[/dim]")
        raise typer.Exit(0)
