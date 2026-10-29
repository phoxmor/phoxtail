"""Tests for cli.server.utils."""

import subprocess
from unittest.mock import patch

from phoxtail.cli.server.utils import ssh_run


@patch("phoxtail.cli.server.utils.subprocess.run")
def test_ssh_run_gives_ssh_no_input(mock_run):
    """A piped answer must reach the prompt after the call, not the server."""
    ssh_run("phoxtail", "203.0.113.5", "cat ~/.phoxtail-project")
    assert mock_run.call_args[1]["stdin"] is subprocess.DEVNULL
