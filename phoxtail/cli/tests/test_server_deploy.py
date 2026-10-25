"""How `server deploy` treats a config file the server already has."""

import subprocess
from unittest.mock import patch

import pytest
import typer

from phoxtail.cli.server.deploy import _upload_config

REMOTE = "~/site/docker-compose.yaml"


def _cat(stdout: str = "", returncode: int = 0, stderr: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(["ssh"], returncode, stdout=stdout, stderr=stderr)


@pytest.fixture
def local(tmp_path):
    path = tmp_path / "docker-compose.prod.yaml"
    path.write_text("image: nginx:1.31\n")
    return path


@pytest.fixture
def server():
    with (
        patch("phoxtail.cli.server.deploy.ssh_check") as check,
        patch("phoxtail.cli.server.deploy.ssh_run") as run,
        patch("phoxtail.cli.server.deploy.scp_to", return_value=True) as scp,
        patch("questionary.confirm") as confirm,
    ):
        yield check, run, scp, confirm


def test_missing_file_is_uploaded(server, local):
    check, run, scp, confirm = server
    check.return_value = False

    _upload_config("u", "1.2.3.4", local, REMOTE, replace=True)

    scp.assert_called_once_with("u", "1.2.3.4", local, REMOTE)
    run.assert_not_called()
    confirm.assert_not_called()


def test_identical_file_is_left_without_asking(server, local):
    check, run, scp, confirm = server
    check.return_value = True
    run.return_value = _cat(local.read_text())

    _upload_config("u", "1.2.3.4", local, REMOTE, replace=True)

    scp.assert_not_called()
    confirm.assert_not_called()


def test_different_file_is_replaced_on_yes(server, local):
    check, run, scp, confirm = server
    check.return_value = True
    run.return_value = _cat("image: nginx:latest\n")
    confirm.return_value.ask.return_value = True

    _upload_config("u", "1.2.3.4", local, REMOTE, replace=True)

    scp.assert_called_once_with("u", "1.2.3.4", local, REMOTE)


@pytest.mark.parametrize("answer", [False, None], ids=["no", "cancelled"])
def test_different_file_is_kept_unless_confirmed(server, local, answer):
    check, run, scp, confirm = server
    check.return_value = True
    run.return_value = _cat("image: nginx:latest\n")
    confirm.return_value.ask.return_value = answer

    _upload_config("u", "1.2.3.4", local, REMOTE, replace=True)

    scp.assert_not_called()


def test_unreadable_server_copy_stops_the_deploy(server, local):
    check, run, scp, confirm = server
    check.return_value = True
    run.return_value = _cat(returncode=1, stderr="Permission denied")

    with pytest.raises(typer.Exit):
        _upload_config("u", "1.2.3.4", local, REMOTE, replace=True)

    scp.assert_not_called()
    confirm.assert_not_called()


def test_existing_file_without_replace_is_never_read(server, local):
    # `.env` holds the secrets, and `nginx.conf` on the server is the HTTPS one:
    # neither may be printed or overwritten.
    check, run, scp, confirm = server
    check.return_value = True

    _upload_config("u", "1.2.3.4", local, "~/site/.env", replace=False)

    run.assert_not_called()
    scp.assert_not_called()
    confirm.assert_not_called()
