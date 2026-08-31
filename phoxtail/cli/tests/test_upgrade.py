"""Tests for the `phoxtail upgrade` check and lock steps."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import typer
from typer.testing import CliRunner

from phoxtail.cli.upgrade import upgrade

app = typer.Typer()
app.command()(upgrade)
runner = CliRunner()

PYPROJECT = """\
[project]
name = "demo"
dependencies = [
    "phoxtail[engine]~=0.1.1",
    "wagtail>=7.4.2,<8.0",
]
"""

TEMPLATE_PYPROJECT = """\
[project]
name = "demo"
dependencies = [
    "phoxtail[engine]~=0.1.1",
]
"""


def _lock(version: str, name: str = "wagtail") -> str:
    return f'version = 1\n\n[[package]]\nname = "{name}"\nversion = "{version}"\n'


def _git_lock(sha: str) -> str:
    return (
        'version = 1\n\n[[package]]\nname = "phoxtail-registry"\nversion = "0.1.0"\n'
        f'source = {{ git = "ssh://git@github.com/phoxmor/phoxtail-registry.git?branch=main#{sha}" }}\n'
    )


def _write(pyproject: str = PYPROJECT, lock: str | None = _lock("7.4.2")) -> None:
    Path("pyproject.toml").write_text(pyproject)
    if lock is not None:
        Path("uv.lock").write_text(lock)


def _ok(*_args, **_kwargs) -> MagicMock:
    return MagicMock(returncode=0, stdout="", stderr="")


class TestCheckStep:
    def test_pinned_dependency_is_recognised(self):
        """A version specifier used to hide the package entirely."""
        _write()
        with patch("phoxtail.cli.upgrade.subprocess.run", side_effect=_ok) as run:
            runner.invoke(app, ["wagtail", "--no-build"])
        assert ["uv", "lock", "--upgrade-package", "wagtail"] in [c[0][0] for c in run.call_args_list]

    def test_transitive_package_is_recognised(self):
        """Not declared in pyproject.toml, but resolved in uv.lock."""
        _write(pyproject=TEMPLATE_PYPROJECT, lock=_lock("7.4.2"))
        with patch("phoxtail.cli.upgrade.subprocess.run", side_effect=_ok) as run:
            runner.invoke(app, ["wagtail", "--no-build"])
        assert run.called

    def test_package_outside_the_graph_is_rejected(self):
        _write(pyproject=TEMPLATE_PYPROJECT, lock=_lock("5.4.0", name="celery"))
        with patch("phoxtail.cli.upgrade.subprocess.run", side_effect=_ok) as run:
            result = runner.invoke(app, ["wagtail", "--no-build"])
        assert result.exit_code == 1
        assert not run.called

    def test_falls_back_to_declarations_without_a_lockfile(self):
        _write(lock=None)
        with patch("phoxtail.cli.upgrade.subprocess.run", side_effect=_ok) as run:
            result = runner.invoke(app, ["wagtail", "--no-build"])
        assert result.exit_code == 0
        assert run.called


class TestLockStep:
    def test_unchanged_lock_syncs_venv_but_skips_the_stack(self):
        _write()
        with patch("phoxtail.cli.upgrade.subprocess.run", side_effect=_ok) as run:
            with patch("phoxtail.cli.upgrade.subprocess.call") as call:
                result = runner.invoke(app, ["wagtail"])
        assert result.exit_code == 0
        # .venv may be behind a pulled lockfile, so sync still runs — but no
        # docker build/migrate/up for an unchanged resolution.
        assert [c[0][0] for c in run.call_args_list] == [
            ["uv", "lock", "--upgrade-package", "wagtail"],
            ["uv", "sync"],
        ]
        assert not call.called

    def test_moved_version_continues_to_sync(self):
        _write()

        def lock_then_bump(cmd, **kwargs):
            if cmd[:2] == ["uv", "lock"]:
                Path("uv.lock").write_text(_lock("7.5.0"))
            return MagicMock(returncode=0, stdout="", stderr="")

        with patch("phoxtail.cli.upgrade.subprocess.run", side_effect=lock_then_bump) as run:
            result = runner.invoke(app, ["wagtail", "--no-build"])
        assert result.exit_code == 0
        assert ["uv", "sync"] in [c[0][0] for c in run.call_args_list]

    def test_a_new_commit_at_the_same_version_continues_to_sync(self):
        """A branch-tracking git dependency moves commit without moving version."""
        _write(pyproject=TEMPLATE_PYPROJECT, lock=_git_lock("a" * 40))

        def lock_then_advance(cmd, **kwargs):
            if cmd[:2] == ["uv", "lock"]:
                Path("uv.lock").write_text(_git_lock("b" * 40))
            return MagicMock(returncode=0, stdout="", stderr="")

        with patch("phoxtail.cli.upgrade.subprocess.run", side_effect=lock_then_advance) as run:
            result = runner.invoke(app, ["phoxtail-registry", "--no-build"])
        assert result.exit_code == 0
        assert ["uv", "sync"] in [c[0][0] for c in run.call_args_list]

    def test_lock_moving_for_another_package_still_syncs(self):
        """`uv lock` re-resolves the whole graph; .venv must not be left behind."""
        _write()

        def lock_then_touch_another(cmd, **kwargs):
            if cmd[:2] == ["uv", "lock"]:
                Path("uv.lock").write_text(_lock("7.4.2") + '\n[[package]]\nname = "celery"\nversion = "5.4.0"\n')
            return MagicMock(returncode=0, stdout="", stderr="")

        with patch("phoxtail.cli.upgrade.subprocess.run", side_effect=lock_then_touch_another) as run:
            result = runner.invoke(app, ["wagtail", "--no-build"])
        assert result.exit_code == 0
        assert ["uv", "sync"] in [c[0][0] for c in run.call_args_list]

    def test_unmoved_transitive_package_points_at_its_pinning_package(self):
        _write(pyproject=TEMPLATE_PYPROJECT, lock=_lock("7.4.2"))
        with patch("phoxtail.cli.upgrade.subprocess.run", side_effect=_ok):
            with patch("phoxtail.cli.upgrade.subprocess.call") as call:
                result = runner.invoke(app, ["wagtail"])
        assert result.exit_code == 0
        assert "phoxtail upgrade phoxtail" in result.output
        assert not call.called

    def test_unmoved_git_package_reports_the_branch_not_a_constraint(self):
        _write(pyproject=TEMPLATE_PYPROJECT, lock=_git_lock("a" * 40))
        with patch("phoxtail.cli.upgrade.subprocess.run", side_effect=_ok):
            with patch("phoxtail.cli.upgrade.subprocess.call") as call:
                result = runner.invoke(app, ["phoxtail-registry"])
        assert result.exit_code == 0
        assert "latest commit" in result.output
        assert not call.called
