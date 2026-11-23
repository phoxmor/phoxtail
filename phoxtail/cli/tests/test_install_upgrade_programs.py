"""Tests for `phoxtail install` and `phoxtail upgrade` meeting a missing program,
and running their containers as the user.

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


class TestContainersRunAsYou:
    """Every compose call carries HOST_UID, so files the containers write are yours.

    The compose file sets each service's user from HOST_UID and HOST_GID,
    falling back to 1000:1000 when they are not set.
    """

    @pytest.mark.parametrize(
        ("command", "args"),
        [(install, ["taggit", "--no-app"]), (upgrade, ["wagtail"])],
        ids=["install", "upgrade"],
    )
    def test_every_compose_call_sets_the_host_user(self, command, args):
        def run(cmd, **kwargs):
            if cmd[:2] == ["uv", "lock"]:
                # A newer wagtail, so upgrade has something to build.
                Path("uv.lock").write_text(
                    'version = 1\n\n[[package]]\nname = "wagtail"\nversion = "7.4.3"\n'
                    '\n[[package]]\nname = "taggit"\nversion = "1.0"\n'
                )
            return MagicMock(returncode=0, stdout="", stderr="")

        with (
            patch("subprocess.run", side_effect=run) as run_mock,
            patch("subprocess.call", return_value=0) as call_mock,
            patch("phoxtail.cli.install.preflight", return_value=(True, "")),
        ):
            result = runner.invoke(_app(command), args)

        compose = [
            c for c in [*run_mock.call_args_list, *call_mock.call_args_list] if c.args[0][:2] == ["docker", "compose"]
        ]
        assert compose, result.output
        assert all("HOST_UID" in (c.kwargs.get("env") or {}) for c in compose), compose
        # It got as far as building, migrating and starting, so those are pinned.
        assert {c.args[0][2] for c in compose} >= {"build", "run", "up"}, compose
