"""Tests for `phoxtail install` and `phoxtail upgrade` meeting a missing program.

Both edit pyproject.toml, lock, sync, then build, migrate and start through
Docker. A program found missing halfway would leave the dependency locked
in but never built, so both check before the first edit.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import typer
from typer.testing import CliRunner

from phoxtail.cli.install import install
from phoxtail.cli.upgrade import upgrade
from phoxtail.cli.utils import tools

runner = CliRunner()

PYPROJECT = """\
[project]
name = "demo"
dependencies = [
    "phoxtail[engine]~=0.1.1",
    "wagtail>=7.4.2,<8.0",
]
"""


def _app(command) -> typer.Typer:
    app = typer.Typer()
    app.command()(command)
    return app


@pytest.fixture(autouse=True)
def project():
    Path("pyproject.toml").write_text(PYPROJECT)
    Path("uv.lock").write_text('version = 1\n\n[[package]]\nname = "wagtail"\nversion = "7.4.2"\n')


@pytest.fixture
def no_side_effects():
    """Fail every program a command gets as far as running, and ask no index.

    The tests below are about what is asked before that; a failing lock
    stops each command right there.
    """
    failed = MagicMock(returncode=1, stdout="", stderr="")
    with (
        patch("subprocess.run", return_value=failed) as run,
        patch("subprocess.call", return_value=1) as call,
        patch("phoxtail.cli.install.preflight", return_value=(True, "")),
    ):
        yield run, call


@pytest.mark.parametrize(
    ("command", "args"),
    [(install, ["taggit"]), (upgrade, ["wagtail"])],
    ids=["install", "upgrade"],
)
class TestPreflight:
    def test_no_docker_refuses_before_touching_the_project(self, command, args, missing, no_side_effects):
        no_docker = missing(tools.COMPOSE)
        result = runner.invoke(_app(command), args)
        run, call = no_side_effects
        assert result.exit_code == 1
        assert no_docker.reason in result.output
        assert "--no-build" in result.output
        assert Path("pyproject.toml").read_text() == PYPROJECT
        run.assert_not_called()
        call.assert_not_called()

    def test_no_build_does_not_need_docker(self, command, args, monkeypatch, no_side_effects):
        asked: list[tuple[tuple[str, ...], bool]] = []

        def check(*programs: str, daemon: bool = False) -> None:
            asked.append((programs, daemon))

        monkeypatch.setattr(tools, "check", check)
        runner.invoke(_app(command), [*args, "--no-build"])
        assert all(tools.COMPOSE not in programs for programs, _daemon in asked)

    def test_docker_is_asked_with_its_daemon(self, command, args, monkeypatch, no_side_effects):
        """The daemon too: a stopped Docker is found before the lock, not after."""
        asked: list[bool] = []

        def check(*programs: str, daemon: bool = False) -> None:
            if tools.COMPOSE in programs:
                asked.append(daemon)

        monkeypatch.setattr(tools, "check", check)
        runner.invoke(_app(command), args)
        assert asked == [True]

    def test_no_uv_refuses_even_without_a_build(self, command, args, missing, no_side_effects):
        no_uv = missing(tools.UV)
        result = runner.invoke(_app(command), [*args, "--no-build"])
        assert result.exit_code == 1
        assert no_uv.reason in result.output
        assert Path("pyproject.toml").read_text() == PYPROJECT
