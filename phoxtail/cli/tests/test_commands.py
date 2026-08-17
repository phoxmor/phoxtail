"""Tests for CLI command modules that are thin subprocess wrappers.

These commands build a command list and pass through to subprocess.call.
Tests verify the correct command is constructed for each invocation.
"""

from unittest.mock import MagicMock, patch

import pytest
import typer
from typer.testing import CliRunner

from phoxtail.cli.docker import app as docker_app
from phoxtail.cli.lint import app as lint_app
from phoxtail.cli.manage import manage as manage_fn
from phoxtail.cli.ssl import app as ssl_app
from phoxtail.cli.test import app as test_app

runner = CliRunner()


class TestDockerUp:
    @patch("phoxtail.cli.docker.subprocess.call", return_value=0)
    def test_default_runs_foreground(self, mock_call):
        runner.invoke(docker_app, ["up"])
        cmd = mock_call.call_args[0][0]
        assert cmd == ["docker", "compose", "up"]

    @patch("phoxtail.cli.docker.subprocess.call", return_value=0)
    def test_detach_flag(self, mock_call):
        runner.invoke(docker_app, ["up", "--detach"])
        cmd = mock_call.call_args[0][0]
        assert "docker" in cmd
        assert "-d" in cmd

    @patch("phoxtail.cli.docker.subprocess.call", return_value=0)
    def test_build_flag(self, mock_call):
        runner.invoke(docker_app, ["up", "--build"])
        # --build triggers a separate `docker compose build` before `up`
        calls = [c[0][0] for c in mock_call.call_args_list]
        assert any("build" in c for c in calls)


class TestDockerDown:
    @patch("phoxtail.cli.docker.subprocess.call", return_value=0)
    def test_basic(self, mock_call):
        runner.invoke(docker_app, ["down"])
        cmd = mock_call.call_args[0][0]
        assert cmd == ["docker", "compose", "down"]


class TestDockerRestart:
    @patch("phoxtail.cli.docker.subprocess.call", return_value=0)
    def test_basic(self, mock_call):
        runner.invoke(docker_app, ["restart"])
        cmd = mock_call.call_args[0][0]
        assert cmd == ["docker", "compose", "restart"]


class TestManage:
    """Test manage command by calling the function directly with proper args."""

    def _make_ctx(self, extra_args: list[str] | None = None):
        ctx = MagicMock()
        ctx.args = extra_args or []
        return ctx

    @patch("phoxtail.cli.manage.sys.exit")
    @patch("phoxtail.cli.manage.subprocess.call", return_value=0)
    def test_passes_command_through(self, mock_call, mock_exit):
        manage_fn(self._make_ctx(), command="createsuperuser")
        cmd = mock_call.call_args[0][0]
        assert cmd == [
            "docker",
            "compose",
            "run",
            "--rm",
            "web",
            "python",
            "manage.py",
            "createsuperuser",
        ]

    @patch("phoxtail.cli.manage.sys.exit")
    @patch("phoxtail.cli.manage.subprocess.call", return_value=0)
    def test_passes_extra_args_through(self, mock_call, mock_exit):
        manage_fn(self._make_ctx(["--dry-run"]), command="makemigrations")
        cmd = mock_call.call_args[0][0]
        assert cmd == [
            "docker",
            "compose",
            "run",
            "--rm",
            "web",
            "python",
            "manage.py",
            "makemigrations",
            "--dry-run",
        ]

    @patch("phoxtail.cli.manage.sys.stdin")
    def test_no_command_non_tty_exits_with_error(self, mock_stdin):
        """Without a command and no TTY, interactive mode should fail."""
        # typer.Exit, not click's — newer typer vendors its own click, and
        # then the two classes are no longer the same object.
        mock_stdin.isatty.return_value = False
        with pytest.raises(typer.Exit):
            manage_fn(self._make_ctx())

    @patch("phoxtail.cli.manage.questionary")
    @patch("phoxtail.cli.manage.sys.stdin")
    @patch("phoxtail.cli.manage.sys.exit")
    @patch("phoxtail.cli.manage.subprocess.call", return_value=0)
    @patch("phoxtail.cli.manage.subprocess.run")
    def test_interactive_mode_selects_command(self, mock_run, mock_call, mock_exit, mock_stdin, mock_questionary):
        """Without a command, interactive mode fetches and presents choices."""
        mock_stdin.isatty.return_value = True
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="[streams]\n    populate_streams\n    setup_streams_groups\n",
        )
        mock_questionary.autocomplete.return_value.ask.return_value = "[streams] populate_streams"

        manage_fn(self._make_ctx())

        cmd = mock_call.call_args[0][0]
        assert cmd == [
            "docker",
            "compose",
            "run",
            "--rm",
            "web",
            "python",
            "manage.py",
            "populate_streams",
        ]

    @patch("phoxtail.cli.manage.questionary")
    @patch("phoxtail.cli.manage.sys.stdin")
    @patch("phoxtail.cli.manage.sys.exit")
    @patch("phoxtail.cli.manage.subprocess.call", return_value=0)
    @patch("phoxtail.cli.manage.subprocess.run")
    def test_interactive_mode_accepts_raw_command_name(
        self, mock_run, mock_call, mock_exit, mock_stdin, mock_questionary
    ):
        """User types a valid command name without selecting from the list."""
        mock_stdin.isatty.return_value = True
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="[django.core]\n    shell\n    showmigrations\n",
        )
        mock_questionary.autocomplete.return_value.ask.return_value = "shell"

        manage_fn(self._make_ctx())

        cmd = mock_call.call_args[0][0]
        assert cmd == [
            "docker",
            "compose",
            "run",
            "--rm",
            "web",
            "python",
            "manage.py",
            "shell",
        ]


class TestTest:
    @patch("phoxtail.cli.test.subprocess.call", return_value=0)
    def test_default_runs_in_docker(self, mock_call):
        runner.invoke(test_app, [])
        cmd = mock_call.call_args[0][0]
        assert cmd == ["docker", "compose", "run", "--rm", "web", "pytest"]

    @patch("phoxtail.cli.test.subprocess.call", return_value=0)
    def test_coverage_flag(self, mock_call):
        runner.invoke(test_app, ["--coverage"])
        cmd = mock_call.call_args[0][0]
        assert "--cov" in cmd
        assert "--cov-report=term-missing" in cmd

    @patch("phoxtail.cli.test.subprocess.call", return_value=0)
    def test_cli_flag_runs_without_docker(self, mock_call):
        runner.invoke(test_app, ["--cli"])
        cmd = mock_call.call_args[0][0]
        assert "docker" not in cmd
        assert "phoxtail/cli/tests/" in cmd

    @patch("phoxtail.cli.test.subprocess.call", return_value=0)
    def test_cli_with_coverage(self, mock_call):
        runner.invoke(test_app, ["--cli", "--coverage"])
        cmd = mock_call.call_args[0][0]
        assert "docker" not in cmd
        assert "--cov=phoxtail" in cmd


class TestLint:
    @patch("phoxtail.cli.lint.subprocess.call", return_value=0)
    def test_default_runs_full_lint(self, mock_call):
        runner.invoke(lint_app, [])
        cmd = mock_call.call_args[0][0]
        shell_cmd = cmd[-1]
        assert "ruff check" in shell_cmd
        assert "--fix" in shell_cmd
        assert "ruff format" in shell_cmd
        assert "djlint" in shell_cmd

    @patch("phoxtail.cli.lint.subprocess.call", return_value=0)
    def test_no_fix(self, mock_call):
        runner.invoke(lint_app, ["--no-fix"])
        cmd = mock_call.call_args[0][0]
        shell_cmd = cmd[-1]
        assert "--fix" not in shell_cmd

    @patch("phoxtail.cli.lint.subprocess.call", return_value=0)
    def test_no_templates(self, mock_call):
        runner.invoke(lint_app, ["--no-templates"])
        cmd = mock_call.call_args[0][0]
        shell_cmd = cmd[-1]
        assert "djlint" not in shell_cmd


class TestSslObtain:
    @patch("phoxtail.cli.ssl.read_env_value")
    @patch("phoxtail.cli.ssl.subprocess.call", return_value=0)
    def test_standard_cert(self, mock_call, mock_env):
        mock_env.side_effect = lambda k: {
            "DOMAIN": "example.com",
            "DOMAIN_EMAIL": "a@b.com",
        }.get(k)
        runner.invoke(ssl_app, ["obtain"])
        cmd = mock_call.call_args[0][0]
        shell_cmd = cmd[-1]
        assert "--webroot" in shell_cmd
        assert "-d example.com" in shell_cmd
        assert "-d www.example.com" in shell_cmd

    @patch("phoxtail.cli.ssl.read_env_value")
    @patch("phoxtail.cli.ssl.subprocess.call", return_value=0)
    def test_wildcard_cert(self, mock_call, mock_env):
        mock_env.side_effect = lambda k: {
            "DOMAIN": "example.com",
            "DOMAIN_EMAIL": "a@b.com",
        }.get(k)
        runner.invoke(ssl_app, ["obtain", "--wildcard"])
        cmd = mock_call.call_args[0][0]
        shell_cmd = cmd[-1]
        assert "--manual" in shell_cmd
        assert "-d *.example.com" in shell_cmd

    @patch("phoxtail.cli.ssl.read_env_value", return_value=None)
    def test_missing_env_vars_errors(self, mock_env):
        result = runner.invoke(ssl_app, ["obtain"])
        assert result.exit_code != 0


class TestSslRenew:
    @patch("phoxtail.cli.ssl.subprocess.call", return_value=0)
    def test_renews_and_reloads(self, mock_call):
        runner.invoke(ssl_app, ["renew"])
        assert mock_call.call_count == 2
        first_cmd = mock_call.call_args_list[0][0][0]
        second_cmd = mock_call.call_args_list[1][0][0]
        assert "renew" in first_cmd
        assert "reload" in second_cmd[-1]
