"""Tests for CLI command modules that are thin subprocess wrappers.

These commands build a command list and pass through to subprocess.call.
Tests verify the correct command is constructed for each invocation.
"""

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from phoxtail.commands.docker import app as docker_app
from phoxtail.commands.lint import app as lint_app
from phoxtail.commands.manage import manage as manage_fn
from phoxtail.commands.ssl import app as ssl_app
from phoxtail.commands.test import app as test_app

runner = CliRunner()


class TestDockerUp:
    @patch("phoxtail.commands.docker.subprocess.call", return_value=0)
    def test_default_runs_detached(self, mock_call):
        runner.invoke(docker_app, ["up"])
        cmd = mock_call.call_args[0][0]
        assert cmd == ["docker", "compose", "up", "-d"]

    @patch("phoxtail.commands.docker.subprocess.call", return_value=0)
    def test_no_detach(self, mock_call):
        runner.invoke(docker_app, ["up", "--no-detach"])
        cmd = mock_call.call_args[0][0]
        assert "docker" in cmd
        assert "-d" not in cmd

    @patch("phoxtail.commands.docker.subprocess.call", return_value=0)
    def test_build_flag(self, mock_call):
        runner.invoke(docker_app, ["up", "--build"])
        cmd = mock_call.call_args[0][0]
        assert "--build" in cmd


class TestDockerDown:
    @patch("phoxtail.commands.docker.subprocess.call", return_value=0)
    def test_basic(self, mock_call):
        runner.invoke(docker_app, ["down"])
        cmd = mock_call.call_args[0][0]
        assert cmd == ["docker", "compose", "down"]


class TestDockerRestart:
    @patch("phoxtail.commands.docker.subprocess.call", return_value=0)
    def test_basic(self, mock_call):
        runner.invoke(docker_app, ["restart"])
        cmd = mock_call.call_args[0][0]
        assert cmd == ["docker", "compose", "restart"]


class TestManage:
    """Test manage callback directly — Typer's CliRunner doesn't support
    allow_extra_args on callback-based sub-apps."""

    def _make_ctx(self, args: list[str]):
        ctx = MagicMock()
        ctx.args = args
        return ctx

    @patch("phoxtail.commands.manage.sys.exit")
    @patch("phoxtail.commands.manage.subprocess.call", return_value=0)
    def test_passes_command_through(self, mock_call, mock_exit):
        manage_fn(self._make_ctx(["createsuperuser"]))
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

    @patch("phoxtail.commands.manage.sys.exit")
    @patch("phoxtail.commands.manage.subprocess.call", return_value=0)
    def test_passes_args_through(self, mock_call, mock_exit):
        manage_fn(self._make_ctx(["makemigrations", "app", "--dry-run"]))
        cmd = mock_call.call_args[0][0]
        assert cmd[-3:] == ["makemigrations", "app", "--dry-run"]

    def test_no_args_exits_with_error(self):
        from click.exceptions import Exit

        with pytest.raises(Exit):
            manage_fn(self._make_ctx([]))


class TestTest:
    @patch("phoxtail.commands.test.subprocess.call", return_value=0)
    def test_default_runs_in_docker(self, mock_call):
        runner.invoke(test_app, [])
        cmd = mock_call.call_args[0][0]
        assert cmd == ["docker", "compose", "run", "--rm", "web", "pytest"]

    @patch("phoxtail.commands.test.subprocess.call", return_value=0)
    def test_coverage_flag(self, mock_call):
        runner.invoke(test_app, ["--coverage"])
        cmd = mock_call.call_args[0][0]
        assert "--cov" in cmd
        assert "--cov-report=term-missing" in cmd

    @patch("phoxtail.commands.test.subprocess.call", return_value=0)
    def test_cli_flag_runs_without_docker(self, mock_call):
        runner.invoke(test_app, ["--cli"])
        cmd = mock_call.call_args[0][0]
        assert "docker" not in cmd
        assert "phoxtail/tests/" in cmd

    @patch("phoxtail.commands.test.subprocess.call", return_value=0)
    def test_cli_with_coverage(self, mock_call):
        runner.invoke(test_app, ["--cli", "--coverage"])
        cmd = mock_call.call_args[0][0]
        assert "docker" not in cmd
        assert "--cov=phoxtail" in cmd


class TestLint:
    @patch("phoxtail.commands.lint.subprocess.call", return_value=0)
    def test_default_runs_full_lint(self, mock_call):
        runner.invoke(lint_app, [])
        cmd = mock_call.call_args[0][0]
        shell_cmd = cmd[-1]
        assert "ruff check" in shell_cmd
        assert "--fix" in shell_cmd
        assert "ruff format" in shell_cmd
        assert "djlint" in shell_cmd

    @patch("phoxtail.commands.lint.subprocess.call", return_value=0)
    def test_no_fix(self, mock_call):
        runner.invoke(lint_app, ["--no-fix"])
        cmd = mock_call.call_args[0][0]
        shell_cmd = cmd[-1]
        assert "--fix" not in shell_cmd

    @patch("phoxtail.commands.lint.subprocess.call", return_value=0)
    def test_no_templates(self, mock_call):
        runner.invoke(lint_app, ["--no-templates"])
        cmd = mock_call.call_args[0][0]
        shell_cmd = cmd[-1]
        assert "djlint" not in shell_cmd


class TestSslObtain:
    @patch("phoxtail.commands.ssl.read_env_value")
    @patch("phoxtail.commands.ssl.subprocess.call", return_value=0)
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

    @patch("phoxtail.commands.ssl.read_env_value")
    @patch("phoxtail.commands.ssl.subprocess.call", return_value=0)
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

    @patch("phoxtail.commands.ssl.read_env_value", return_value=None)
    def test_missing_env_vars_errors(self, mock_env):
        result = runner.invoke(ssl_app, ["obtain"])
        assert result.exit_code != 0


class TestSslRenew:
    @patch("phoxtail.commands.ssl.subprocess.call", return_value=0)
    def test_renews_and_reloads(self, mock_call):
        runner.invoke(ssl_app, ["renew"])
        assert mock_call.call_count == 2
        first_cmd = mock_call.call_args_list[0][0][0]
        second_cmd = mock_call.call_args_list[1][0][0]
        assert "renew" in first_cmd
        assert "reload" in second_cmd[-1]
