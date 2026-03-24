"""Serve and build the Phoxtail documentation site."""

import subprocess
import sys
import webbrowser
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel

app = typer.Typer()
console = Console()

_PACKAGE_DOCS_DIR = Path(__file__).resolve().parent.parent / "docs"


def _get_docs_dir() -> Path:
    """Return the docs directory.

    Prefers a local source checkout over the installed package so that
    live-reload works during development.
    """
    local = Path.cwd() / "phoxtail" / "docs"
    if (local / "mkdocs.yml").exists():
        return local
    return _PACKAGE_DOCS_DIR


def _check_zensical():
    """Ensure zensical is installed."""
    try:
        import zensical  # noqa: F401
    except ImportError:
        console.print(
            Panel(
                "Docs dependencies are not installed.\n"
                "Run: [bold]pip install phoxtail\\[docs][/bold]",
                title="[red]Missing dependency[/red]",
                border_style="red",
                expand=False,
            )
        )
        raise typer.Exit(code=1)


def _check_docs_exist(mkdocs_yml: Path):
    """Ensure mkdocs.yml exists."""
    if not mkdocs_yml.exists():
        console.print(
            Panel(
                "Documentation files not found.\n"
                "Expected mkdocs.yml at: " + str(mkdocs_yml),
                title="[red]Missing docs[/red]",
                border_style="red",
                expand=False,
            )
        )
        raise typer.Exit(code=1)


@app.callback(invoke_without_command=True)
def docs(
    ctx: typer.Context,
    port: int = typer.Option(8000, "--port", "-p", help="Port to serve on"),
    host: str = typer.Option("127.0.0.1", "--host", help="Host to bind to"),
    open_browser: bool = typer.Option(
        True, "--open/--no-open", "-o", help="Open in browser after starting"
    ),
):
    """Serve the Phoxtail documentation locally.

    Run without a subcommand to start the dev server with live reload.
    Use 'phoxtail docs build' to generate a static site.

    Examples:
        phoxtail docs
        phoxtail docs --no-open
        phoxtail docs --port 9000
        phoxtail docs build
        phoxtail docs build --clean
    """
    if ctx.invoked_subcommand is not None:
        return

    docs_dir = _get_docs_dir()
    mkdocs_yml = docs_dir / "mkdocs.yml"

    _check_zensical()
    _check_docs_exist(mkdocs_yml)

    if open_browser:
        webbrowser.open(f"http://{host}:{port}")

    subprocess.run(
        [
            sys.executable,
            "-m",
            "zensical",
            "serve",
            "--dev-addr",
            f"{host}:{port}",
            "--config-file",
            str(mkdocs_yml),
        ],
        cwd=docs_dir,
    )


@app.command()
def build(
    clean: bool = typer.Option(
        False, "--clean", "-c", help="Clear the cache before building"
    ),
) -> None:
    """Build the documentation as a static site.

    Generates HTML output in the configured site_dir (default: site/).

    Examples:
        phoxtail docs build
        phoxtail docs build --clean
    """
    docs_dir = _get_docs_dir()
    mkdocs_yml = docs_dir / "mkdocs.yml"

    _check_zensical()
    _check_docs_exist(mkdocs_yml)

    cmd = [
        sys.executable,
        "-m",
        "zensical",
        "build",
        "--config-file",
        str(mkdocs_yml),
    ]
    if clean:
        cmd.append("--clean")

    result = subprocess.run(cmd, cwd=docs_dir)
    if result.returncode == 0:
        console.print("[green bold]✓ Documentation built successfully[/green bold]")
    sys.exit(result.returncode)
