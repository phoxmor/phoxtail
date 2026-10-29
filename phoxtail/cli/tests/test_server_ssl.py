"""Tests for the renewal cron step of `phoxtail server ssl`."""

import subprocess
from unittest.mock import patch

import pytest

from phoxtail.cli.server.ssl import _install_renewal_cron

MARKER = "phoxtail-ssl-mysite"
ENTRY = (
    "0 3 1,15 * * cd $HOME/mysite && docker compose run --rm -T --no-deps certbot renew -q"
    f" && docker compose exec -T nginx nginx -s reload  # {MARKER}"
)
OLD = (
    "0 3 1,15 * * cd $HOME/mysite && docker compose run --rm -T certbot renew -q"
    f" && docker compose exec -T nginx nginx -s reload  # {MARKER}"
)


def _read(stdout=""):
    return subprocess.CompletedProcess([], 0, stdout=stdout, stderr="")


@pytest.fixture
def server():
    """ssh_run returns the server's marked line; ssh_check runs the install."""
    with (
        patch("phoxtail.cli.server.ssl.ssh_run") as ssh_run,
        patch("phoxtail.cli.server.ssl.ssh_check", return_value=True) as ssh_check,
        patch("questionary.confirm") as confirm,
    ):
        yield ssh_run, ssh_check, confirm


def test_current_line_is_left_alone(server):
    ssh_run, ssh_check, confirm = server
    ssh_run.return_value = _read(ENTRY + "\n")
    assert _install_renewal_cron("phoxtail", "203.0.113.5", ENTRY, MARKER)
    ssh_check.assert_not_called()
    confirm.assert_not_called()


def test_missing_line_is_installed_without_asking(server):
    ssh_run, ssh_check, confirm = server
    ssh_run.return_value = _read("")
    assert _install_renewal_cron("phoxtail", "203.0.113.5", ENTRY, MARKER)
    confirm.assert_not_called()
    assert f"echo '{ENTRY}'" in ssh_check.call_args[0][2]


def test_outdated_line_is_replaced_on_yes(server):
    ssh_run, ssh_check, confirm = server
    ssh_run.return_value = _read(OLD + "\n")
    confirm.return_value.ask.return_value = True
    assert _install_renewal_cron("phoxtail", "203.0.113.5", ENTRY, MARKER)
    confirm.assert_called_once_with("Replace it?", default=False)
    ssh_check.assert_called_once()


def test_outdated_line_is_kept_on_no(server):
    ssh_run, ssh_check, confirm = server
    ssh_run.return_value = _read(OLD + "\n")
    confirm.return_value.ask.return_value = False
    assert not _install_renewal_cron("phoxtail", "203.0.113.5", ENTRY, MARKER)
    ssh_check.assert_not_called()


def test_failed_install_reports_no_cron(server):
    ssh_run, ssh_check, _ = server
    ssh_run.return_value = _read("")
    ssh_check.return_value = False
    assert not _install_renewal_cron("phoxtail", "203.0.113.5", ENTRY, MARKER)


def test_the_read_matches_only_our_marker(server):
    ssh_run, _, _ = server
    ssh_run.return_value = _read(ENTRY)
    _install_renewal_cron("phoxtail", "203.0.113.5", ENTRY, MARKER)
    assert ssh_run.call_args[0][2] == f"crontab -l 2>/dev/null | grep -E -- '# {MARKER}[[:space:]]*$'"


def test_install_command_against_a_real_crontab(server, tmp_path):
    """Run the exact shell against a stand-in crontab holding other entries."""
    ssh_run, ssh_check, confirm = server
    table = tmp_path / "table"
    table.write_text(
        "*/5 * * * * /usr/local/bin/backup.sh\n"
        f"{OLD}\n"
        f"{OLD}  \n"  # a duplicate, with trailing spaces, collapses too
        "0 4 * * * renew  # phoxtail-ssl-mysite-staging\n"  # another project's marker
    )
    fake = tmp_path / "crontab"
    # Like the real one, it takes the whole new table before installing it.
    fake.write_text(
        f'#!/bin/sh\nif [ "$1" = -l ]; then cat {table}; else cat > {table}.new && mv {table}.new {table}; fi\n'
    )
    fake.chmod(0o755)

    def run_on_server(user, ip, command):
        env = {"PATH": f"{tmp_path}:/usr/bin:/bin"}
        return subprocess.run(["sh", "-c", command], env=env).returncode == 0

    ssh_run.return_value = _read(f"{OLD}\n{OLD}\n")
    ssh_check.side_effect = run_on_server
    confirm.return_value.ask.return_value = True

    assert _install_renewal_cron("phoxtail", "203.0.113.5", ENTRY, MARKER)
    assert table.read_text().splitlines() == [
        "*/5 * * * * /usr/local/bin/backup.sh",
        "0 4 * * * renew  # phoxtail-ssl-mysite-staging",
        ENTRY,
    ]
