"""phoxtail install — manage phoxtail packages in a project."""

import os
import re
import subprocess
import sys
import tomllib
from pathlib import Path

import httpx
import typer
import yaml
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt

from phoxtail.cli.hatch import INSTALL_MARKER
from phoxtail.cli.utils.config import get_project_name, slugify
from phoxtail.cli.utils.docker import collect_package_compose_fragments
from phoxtail.cli.utils.packages import is_declared, module_guess
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
    ("populate", "Populate"),
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


def _pypi_releases(package: str) -> list[str] | None:
    """Versions of `package` released on PyPI.

    An empty list means PyPI answered and has no such project; None means it
    could not answer at all, which is not the same thing — an unreachable
    index must never be reported to the user as a missing package.

    Asked over the JSON API rather than uv: `uv pip index` is gone as of uv
    0.11, and no other uv subcommand lists the versions of a package that is
    not installed.
    """
    try:
        response = httpx.get(f"https://pypi.org/pypi/{package}/json", timeout=10.0, follow_redirects=True)
    except httpx.HTTPError:
        return None
    if response.status_code == 404:
        return []
    if response.status_code != 200:
        return None
    try:
        return sorted(response.json().get("releases", {}))
    except ValueError:
        return None


def _preflight_pypi(package: str) -> tuple[bool, str]:
    # A package is missing only when PyPI says so: None means the index never
    # answered, which must not be reported as a package that does not exist.
    if _pypi_releases(package) == []:
        return False, (
            f"[bold]{package}[/bold] was not found on PyPI.\n"
            "If this is a private package, provide its git URL:\n"
            f"  [cyan]phoxtail install --url ssh://git@github.com/your-org/{package}.git[/cyan]"
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


class NoInsertionPoint(Exception):
    """pyproject.toml has no [project] dependencies array to append to."""


def _add_dependency(content: str, package: str) -> str:
    """Append `package` to [project].dependencies, or return `content` if already declared.

    Raises NoInsertionPoint when the array cannot be found — returning the
    text unchanged would let every later step report success for a package
    that was never declared.
    """
    # A pinned entry ("wagtail>=7.4.2,<8.0") declares the package just as much
    # as a bare one does — appending a second entry for it would leave the
    # project with two conflicting requirements for one distribution.
    # runtime_only: a dev-group or extras entry never reaches the production
    # image, so it must not block declaring the package as a runtime dependency.
    if is_declared(content, package, runtime_only=True):
        return content
    # Anchored inside the [project] table: keying off what follows the array
    # instead landed every install in dependency-groups.dev, which the
    # production image drops with `uv sync --no-dev`.
    header = re.search(r"(?m)^\[project\][ \t]*$", content)
    if header is None:
        raise NoInsertionPoint("no [project] table")
    tail = content[header.end() :]
    next_table = re.search(r"(?m)^\[", tail)
    table = tail[: next_table.start()] if next_table else tail
    array = re.search(r"(?ms)^dependencies\s*=\s*\[\n.*?^\]", table)
    if array is not None:
        closing_bracket = header.end() + array.end() - 1
        return content[:closing_bracket] + f'    "{package}",\n' + content[closing_bracket:]
    # `dependencies = []` and single-line arrays are valid TOML too.
    inline = re.search(r"(?m)^dependencies\s*=\s*\[(?P<inner>[^\[\]]*)\]", table)
    if inline is None:
        raise NoInsertionPoint("no dependencies array under [project]")
    inner = inline.group("inner").strip().rstrip(",")
    new_inner = f'{inner}, "{package}"' if inner else f'"{package}"'
    start, end = header.end() + inline.start("inner"), header.end() + inline.end("inner")
    return content[:start] + new_inner + content[end:]


def _add_uv_source(content: str, package: str, git_url: str, branch: str) -> str:
    # Keyed on the package, not the URL: the same URL under another package's
    # key must not stop this one from getting a source, and a second entry for
    # an already-sourced package would be a duplicate TOML key.
    if re.search(rf"(?m)^{re.escape(package)}\s*=\s*{{", content):
        return content
    source_line = f'{package} = {{ git = "{git_url}", branch = "{branch}" }}'
    header = re.search(r"(?m)^\[tool\.uv\.sources\][ \t]*$", content)
    if header:
        # Right under the table header — appended to the end of the file, the
        # key would belong to whichever table happens to come last.
        return content[: header.end()] + f"\n{source_line}" + content[header.end() :]
    # The hatched template has [tool.uv] but no [tool.uv.sources]; dropping the
    # source silently would send `uv lock` to PyPI for a private package.
    return content.rstrip() + f"\n\n[tool.uv.sources]\n{source_line}\n"


def _shipped_modules(dist_info: Path) -> list[str]:
    """Top-level modules recorded in a distribution's installed metadata.

    setuptools writes top_level.txt; hatchling and flit do not, so fall back
    to the RECORD manifest every installer writes.
    """
    top_level = dist_info / "top_level.txt"
    if top_level.exists():
        return [line.strip() for line in top_level.read_text().splitlines() if line.strip()]
    record = dist_info / "RECORD"
    if not record.exists():
        return []
    modules = []
    for line in record.read_text().splitlines():
        path = line.split(",")[0]
        head, _, rest = path.partition("/")
        # `..` entries live outside site-packages (scripts, data files).
        if head.startswith(".") or head.endswith((".dist-info", ".data")) or head == "__pycache__":
            continue
        if rest:
            modules.append(head)
        elif head.endswith(".py"):
            modules.append(head[: -len(".py")])
    return list(dict.fromkeys(modules))


def _module_candidates(site_packages: Path, package: str) -> list[str]:
    """Top-level modules a distribution installs, best guess first.

    The distribution name is only a guess at the module name — django-cors-headers
    installs `corsheaders` — so consult the installed metadata, which records what
    the wheel actually shipped.
    """
    normalized = module_guess(package)
    candidates = [normalized]
    for dist_info in site_packages.glob("*.dist-info"):
        if module_guess(dist_info.name.split("-")[0]) != normalized:
            continue
        candidates += _shipped_modules(dist_info)
    return list(dict.fromkeys(candidates))


def _is_django_app(module: Path) -> bool:
    """Whether a module looks like a Django app rather than a plain library.

    Importability is not the test: `httpx` and `redis` are importable packages
    that must never reach INSTALLED_APPS. An app carries an AppConfig, models,
    or migrations.
    """
    return module.is_dir() and (
        (module / "apps.py").exists() or (module / "models.py").exists() or (module / "migrations").is_dir()
    )


def _detect_app_info(package: str) -> tuple[str, str] | tuple[None, None]:
    """Return (apps_entry, django_label) for the installed package, or (None, None).

    apps_entry   — the string that belongs in INSTALLED_APPS (Python module name).
    django_label — the short label Django registers the app under; comes from
                   AppConfig.label in apps.py, falling back to the last dotted
                   segment of AppConfig.name.
    """
    for site_packages in sorted(Path(".venv").glob("lib/python*/site-packages")):
        for module_name in _module_candidates(site_packages, package):
            module = site_packages / module_name
            if not _is_django_app(module):
                continue
            django_label = module_name
            apps_py = module / "apps.py"
            if apps_py.exists():
                content = apps_py.read_text()
                m = re.search(r'\blabel\s*=\s*["\']([^"\']+)["\']', content)
                if m:
                    django_label = m.group(1)
                else:
                    m = re.search(r'\bname\s*=\s*["\']([^"\']+)["\']', content)
                    if m:
                        django_label = m.group(1).rsplit(".", 1)[-1]
            return module_name, django_label
    return None, None


def _confirm_installed_app(package: str, detected: str | None, *, app: str | None, no_app: bool) -> str | None:
    """Ask whether this package belongs in INSTALLED_APPS, and under what name.

    `detected` is only a suggestion — a package can be a Django app with none
    of the tell-tale files, and an importable module is not an app just because
    it installed cleanly. The flags answer for non-interactive runs, where a
    prompt would hang.
    """
    if no_app:
        return None
    if app:
        return app
    if not sys.stdin.isatty():
        return detected
    if detected:
        if Confirm.ask(f"Register [cyan]{detected}[/cyan] in INSTALLED_APPS?", default=True):
            return detected
        return None
    if not Confirm.ask(f"[dim]{package} does not look like a Django app.[/dim] Register it anyway?", default=False):
        return None
    return Prompt.ask("Module name for INSTALLED_APPS", default=module_guess(package)).strip() or None


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
        "image_name": f"{slugify(project_name)}/{slugify(project_name)}:latest",
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
    app: str = typer.Option(None, "--app", help="Module to add to INSTALLED_APPS, skipping the prompt"),
    no_app: bool = typer.Option(False, "--no-app", help="Do not touch INSTALLED_APPS"),
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
        try:
            already_declared = pyproject_path.exists() and is_declared(
                pyproject_path.read_text(), package, runtime_only=True
            )
        except tomllib.TOMLDecodeError as exc:
            steps["check"] = "failed"
            _redraw(package, steps, details)
            console.print(f"[red]Could not parse pyproject.toml:[/red] {exc}")
            raise typer.Exit(1) from exc
        if already_declared:
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
        try:
            updated_content = _add_dependency(original_content, package)
        except NoInsertionPoint as exc:
            steps["lock"] = "failed"
            _redraw(package, steps, details)
            console.print(
                f"[red]Could not add {package} to pyproject.toml:[/red] {exc}.\n"
                f'Add [cyan]"{package}"[/cyan] to [project].dependencies by hand, then run '
                "[cyan]uv lock[/cyan]."
            )
            raise typer.Exit(1) from exc
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
        # Whether a package belongs in INSTALLED_APPS is the installer's call,
        # not something to infer: detection only picks the default answer.
        _redraw(package, steps, details, step_idx["register"])
        with console.status("  [dim]detecting app label...[/dim]"):
            detected, detected_label = _detect_app_info(package)
        apps_entry = _confirm_installed_app(package, detected, app=app, no_app=no_app)
        # The label follows the decision, not the detection: an app the
        # installer declined must not be populated, and a module they named
        # themselves gets Django's default label — the module name.
        django_label = detected_label if apps_entry == detected else apps_entry
        if apps_entry is None:
            steps["register"] = "skipped"
            details["register"] = "not a Django app" if detected is None else "left out on request"
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

        # --- Populate ---
        if steps.get("migrate") in ("skipped", "failed"):
            steps["populate"] = "skipped"
            details["populate"] = "migrate not run"
        elif django_label is None:
            steps["populate"] = "skipped"
            details["populate"] = "not registered as an app"
        else:
            _redraw(package, steps, details, step_idx["populate"])
            rc = subprocess.call(
                [
                    "docker",
                    "compose",
                    "run",
                    "--rm",
                    "-T",
                    "web",
                    "python",
                    "manage.py",
                    "populate_streams",
                    "--app",
                    django_label,
                ],
            )
            steps["populate"] = "done" if rc == 0 else "failed"

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
