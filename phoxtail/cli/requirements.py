"""Requirements management commands."""

import subprocess
from pathlib import Path

import typer
from rich.console import Console

from phoxtail.cli.utils.venv import check_uv_installed

app = typer.Typer()
console = Console()


@app.command()
def compile(
    upgrade: bool = typer.Option(
        False,
        "--upgrade",
        "-u",
        help="Upgrade all packages to their latest versions",
    ),
    input_file: Path = typer.Option(
        Path("requirements.in"),
        "--input",
        "-i",
        help="Input requirements file",
    ),
    output_file: Path = typer.Option(
        Path("requirements.txt"),
        "--output",
        "-o",
        help="Output requirements file",
    ),
) -> None:
    """Compile requirements.in to requirements.txt using uv.

    This uses uv's built-in pip-compile replacement, which is faster and
    has no compatibility issues with pip versions. Works even before
    Docker containers are built.
    """
    if not input_file.exists():
        console.print(f"[red]Error:[/red] {input_file} not found")
        raise typer.Exit(1)

    check_uv_installed()

    console.print(f"Compiling {input_file} → {output_file}...", style="cyan bold")

    cmd = ["uv", "pip", "compile"]
    if upgrade:
        cmd.append("--upgrade")
    cmd.extend(["--output-file", str(output_file), str(input_file)])

    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        console.print("✓ Requirements compiled successfully", style="green bold")

        if result.stderr:
            for line in result.stderr.strip().split("\n"):
                if line.strip():
                    console.print(f"  {line}", style="dim")
    except subprocess.CalledProcessError as e:
        console.print("[red]Error compiling requirements:[/red]")
        if e.stderr:
            console.print(e.stderr, style="red")
        raise typer.Exit(1)
