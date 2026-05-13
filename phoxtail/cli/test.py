"""Test runner commands."""

import subprocess
import sys

import typer
from rich.console import Console

from phoxtail.cli.utils.docker import docker_env

app = typer.Typer(
    add_completion=False,
    invoke_without_command=True,
    context_settings={"allow_extra_args": True, "allow_interspersed_args": False},
)
console = Console()


@app.callback()
def test(
    ctx: typer.Context,
    coverage: bool = typer.Option(False, "--coverage", "--cov", help="Run with coverage report"),
    cli: bool = typer.Option(False, "--cli", help="Run CLI tests only (no Docker required)"),
) -> None:
    """Run the test suite.

    By default, runs Django tests inside the Docker web container.
    Use --cli to run CLI tests directly (fast, no Docker).

    Extra arguments are passed through to pytest.

    Examples:
        phoxtail test
        phoxtail test --coverage
        phoxtail test --cli
        phoxtail test -- -x -k test_something
        phoxtail test -- booking/subscriptions/tests
    """
    if cli:
        cmd = [sys.executable, "-m", "pytest", "phoxtail/cli/tests/"]
        if coverage:
            cmd.extend(["--cov=phoxtail", "--cov-report=term-missing"])
        cmd.extend(ctx.args)
        sys.exit(subprocess.call(cmd))
    else:
        cmd = ["docker", "compose", "run", "--rm", "web", "pytest"]
        if coverage:
            cmd.extend(["--cov", "--cov-report=term-missing"])
        cmd.extend(ctx.args)
        sys.exit(subprocess.call(cmd, env=docker_env()))
