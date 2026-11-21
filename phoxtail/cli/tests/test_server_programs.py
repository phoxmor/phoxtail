"""Tests for the server commands meeting a missing program, and finding themselves.

`server provision` creates a server that is paid for from that moment, and
only then runs ssh-keygen and ssh; `server deploy` and `server ssl` change
the server before they copy files with scp. All three check first.
"""

import sys
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from phoxtail.__main__ import app
from phoxtail.cli.utils import tools

runner = CliRunner()


class TestProvision:
    def test_no_ssh_keygen_refuses_before_any_provider_is_asked(self, missing):
        no_keygen = missing(tools.SSH_KEYGEN)
        with patch("phoxtail.cli.server.provision._ask_provider") as ask:
            result = runner.invoke(app, ["server", "provision"])
        assert result.exit_code == 1
        assert no_keygen.reason in result.output
        ask.assert_not_called()

    def test_dry_run_creates_nothing_so_needs_no_ssh(self, missing):
        missing(tools.SSH)
        with patch("phoxtail.cli.server.provision._ask_provider", return_value=None) as ask:
            result = runner.invoke(app, ["server", "provision", "--dry-run"])
        assert result.exit_code == 0
        ask.assert_called_once()


class TestDeploy:
    def test_no_scp_refuses_before_reaching_the_server(self, missing):
        no_scp = missing(tools.SCP)
        with patch("phoxtail.cli.server.deploy.ssh_check") as ssh_check:
            result = runner.invoke(app, ["server", "deploy", "203.0.113.5"])
        assert result.exit_code == 1
        assert no_scp.reason in result.output
        ssh_check.assert_not_called()

    def test_configuration_is_generated_by_this_same_cli(self):
        """Not whichever `phoxtail` PATH holds: run as `python -m`, there may be none."""
        with (
            patch("phoxtail.cli.server.deploy.ssh_check", return_value=True),
            patch("phoxtail.cli.server.deploy.ssh_run", return_value=MagicMock(returncode=0, stdout="")),
            patch("phoxtail.cli.server.deploy.verify_server_identity"),
            # Stop at the first generated file.
            patch("phoxtail.cli.server.deploy.subprocess.call", return_value=1) as call,
        ):
            result = runner.invoke(app, ["server", "deploy", "203.0.113.5"])
        assert result.exit_code == 1
        assert call.call_args.args[0][:5] == [sys.executable, "-m", "phoxtail", "env", "create"]


class TestSsl:
    def test_no_ssh_refuses_before_reaching_the_server(self, missing):
        no_ssh = missing(tools.SSH)
        with patch("phoxtail.cli.server.ssl.ssh_check") as ssh_check:
            result = runner.invoke(
                app, ["server", "ssl", "203.0.113.5", "--domain", "example.com", "--email", "ops@example.com"]
            )
        assert result.exit_code == 1
        assert no_ssh.reason in result.output
        ssh_check.assert_not_called()
