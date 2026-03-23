"""Virtual environment management utilities."""

import shutil
import subprocess
from pathlib import Path

import typer
from rich.console import Console

console = Console()


def check_uv_installed() -> None:
    """Check if uv is installed and available. Exits if not found."""
    if not shutil.which("uv"):
        console.print("[red]Error:[/red] uv is not installed", style="bold")
        console.print("\nInstall uv with:")
        console.print("  curl -LsSf https://astral.sh/uv/install.sh | sh")
        console.print("  or: pip install uv")
        raise typer.Exit(1)


class ToolVenv:
    """Manages an isolated virtual environment for build tools using uv."""

    def __init__(self, project_root: Path | None = None):
        """Initialize the tool venv manager.

        Args:
            project_root: Root directory of the project. Defaults to current directory.
        """
        self.project_root = project_root or Path.cwd()
        self.venv_dir = self.project_root / ".phoxtail" / "venv"
        self.python_path = self.venv_dir / "bin" / "python"

    def exists(self) -> bool:
        """Check if the tool venv exists."""
        return self.venv_dir.exists() and self.python_path.exists()

    def _check_uv_installed(self) -> None:
        """Check if uv is installed and available."""
        check_uv_installed()

    def create(self) -> None:
        """Create the tool virtual environment using uv."""
        if self.exists():
            console.print("✓ Tool venv already exists", style="dim")
            return

        self._check_uv_installed()

        console.print("Creating tool venv with uv...", style="yellow")
        self.venv_dir.parent.mkdir(parents=True, exist_ok=True)

        subprocess.run(
            ["uv", "venv", str(self.venv_dir)],
            check=True,
            capture_output=True,
        )
        console.print("✓ Tool venv created", style="green")

    def ensure_package(self, package: str, upgrade: bool = False) -> None:
        """Ensure a package is installed in the tool venv using uv.

        Args:
            package: Package name to install
            upgrade: Whether to upgrade the package if already installed
        """
        if not self.exists():
            self.create()

        self._check_uv_installed()

        # Check if package is already installed
        if not upgrade:
            result = subprocess.run(
                ["uv", "pip", "show", "--python", str(self.python_path), package],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                console.print(f"✓ {package} already installed", style="dim")
                return

        console.print(f"Installing {package} with uv...", style="yellow")
        cmd = ["uv", "pip", "install", "--python", str(self.python_path)]
        if upgrade:
            cmd.append("--upgrade")
        cmd.append(package)

        subprocess.run(cmd, check=True, capture_output=True)
        console.print(f"✓ {package} installed", style="green")

    def run_command(self, command: list[str], **kwargs) -> subprocess.CompletedProcess:
        """Run a command using the tool venv's Python.

        Args:
            command: Command and arguments to run
            **kwargs: Additional arguments to pass to subprocess.run

        Returns:
            CompletedProcess instance
        """
        if not self.exists():
            raise RuntimeError("Tool venv does not exist. Run create() first.")

        # Use the venv's Python to run the command
        full_command = [str(self.python_path), "-m"] + command
        return subprocess.run(full_command, **kwargs)
