"""Tests for `phoxtail server ssl`: the certificate's names and the renewal cron."""

import subprocess
from unittest.mock import patch

import pytest
import typer
from typer.testing import CliRunner

from phoxtail.cli.server.ssl import _certificate_names, _install_renewal_cron, ssl

MARKER = "phoxtail-ssl-mysite"
ENTRY = (
    "0 3 1,15 * * cd $HOME/mysite && docker compose run --rm -T --no-deps certbot renew -q"
    f" && docker compose exec -T nginx nginx -s reload  # {MARKER}"
)
OLD = (
    "0 3 1,15 * * cd $HOME/mysite && docker compose run --rm -T certbot renew -q"
    f" && docker compose exec -T nginx nginx -s reload  # {MARKER}"
)

IP = "203.0.113.5"

LISTING_5 = """\
Found the following matching certs:
  Certificate Name: example.com
    Serial Number: 565e1eafecac11dec963e10b421971f0d6d
    Key Type: ECDSA
    Identifiers: example.com www.example.com
    Expiry Date: 2027-01-31 20:34:06+00:00 (VALID: 89 days)
"""

app = typer.Typer()
app.command()(ssl)


def _read(stdout="", returncode=0):
    return subprocess.CompletedProcess([], returncode, stdout=stdout, stderr="")


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


def test_names_from_a_certbot_5_listing():
    assert _certificate_names(LISTING_5) == {"example.com", "www.example.com"}


def test_names_from_an_older_listing():
    assert _certificate_names(LISTING_5.replace("Identifiers:", "Domains:")) == {
        "example.com",
        "www.example.com",
    }


def test_no_certificate_holds_no_names():
    assert _certificate_names("Found the following matching certs:\n\n") == set()


@pytest.fixture
def reachable(monkeypatch):
    """A reachable server; records certbot's request and nginx's www flag."""
    monkeypatch.setattr("phoxtail.cli.server.ssl.get_project_name", lambda: "mysite")
    with (
        patch("phoxtail.cli.server.ssl.ssh_check", return_value=True),
        patch("phoxtail.cli.server.ssl.ssh_run") as ssh_run,
        patch("phoxtail.cli.server.ssl.ssh_live", return_value=0) as ssh_live,
        patch("phoxtail.cli.server.ssl.scp_to", return_value=True),
        patch("phoxtail.cli.server.ssl.subprocess.call", return_value=0) as nginx,
        patch("phoxtail.cli.server.ssl._install_renewal_cron", return_value=True),
    ):
        ssh_run.return_value = _read()
        yield ssh_run, ssh_live, nginx


def _run(*args, resolves=("example.com", "mcp.example.com", "www.example.com")):
    with patch("phoxtail.cli.server.ssl._dns_resolves_to", side_effect=lambda name, ip: name in resolves):
        return CliRunner().invoke(app, [IP, "--domain", "example.com", "--email", "ops@example.com", *args])


def _certbot(ssh_live):
    return next(c.args[2] for c in ssh_live.call_args_list if "certonly" in c.args[2])


def _requested(ssh_live):
    """The -d names of the certbot request, in order."""
    parts = _certbot(ssh_live).split()
    return [parts[i + 1] for i, part in enumerate(parts) if part == "-d"]


def _nginx_www(nginx):
    flags = nginx.call_args.args[0]
    return "--www" in flags and "--no-www" not in flags


def test_www_is_included_when_it_points_here(reachable):
    _, ssh_live, nginx = reachable
    result = _run()
    assert result.exit_code == 0, result.output
    assert _requested(ssh_live) == ["example.com", "mcp.example.com", "www.example.com"]
    assert _nginx_www(nginx)


def test_www_is_left_out_when_it_does_not_point_here(reachable):
    _, ssh_live, nginx = reachable
    result = _run(resolves=("example.com", "mcp.example.com"))
    assert result.exit_code == 0, result.output
    assert _requested(ssh_live) == ["example.com", "mcp.example.com"]
    assert not _nginx_www(nginx)


def test_explicit_www_fails_when_it_does_not_point_here(reachable):
    _, ssh_live, _ = reachable
    result = _run("--www", resolves=("example.com", "mcp.example.com"))
    assert result.exit_code == 1
    assert "www.example.com does not resolve" in result.output
    ssh_live.assert_not_called()


def test_no_www_leaves_it_out_even_when_it_points_here(reachable):
    _, ssh_live, nginx = reachable
    result = _run("--no-www")
    assert result.exit_code == 0, result.output
    assert _requested(ssh_live) == ["example.com", "mcp.example.com"]
    assert not _nginx_www(nginx)


def test_skipping_dns_needs_an_explicit_www_choice(reachable):
    _, ssh_live, _ = reachable
    result = _run("--skip-dns-check")
    assert result.exit_code == 1
    assert "--no-www" in result.output
    ssh_live.assert_not_called()


def test_a_certificate_missing_www_is_expanded_in_its_own_lineage(reachable):
    """The bug this guards: a rerun once skipped issuance because mcp. was there."""
    ssh_run, ssh_live, _ = reachable
    ssh_run.return_value = _read(LISTING_5.replace("www.example.com", "mcp.example.com"))
    result = _run()
    assert result.exit_code == 0, result.output
    assert _requested(ssh_live) == ["example.com", "mcp.example.com", "www.example.com"]
    command = _certbot(ssh_live)
    assert "--cert-name example.com " in command
    assert "--non-interactive" in command


def test_a_certificate_covering_every_name_is_kept(reachable):
    ssh_run, ssh_live, nginx = reachable
    ssh_run.return_value = _read(LISTING_5.replace("www.example.com", "mcp.example.com www.example.com"))
    result = _run()
    assert result.exit_code == 0, result.output
    assert not any("certonly" in c.args[2] for c in ssh_live.call_args_list)
    assert _nginx_www(nginx)


def test_a_held_name_is_never_dropped(reachable):
    """--no-www against a certificate with www keeps www, and nginx serves it."""
    ssh_run, ssh_live, nginx = reachable
    ssh_run.return_value = _read(LISTING_5)
    result = _run("--no-www")
    assert result.exit_code == 0, result.output
    assert _requested(ssh_live) == ["example.com", "mcp.example.com", "www.example.com"]
    assert _nginx_www(nginx)


def test_an_unread_listing_stops_before_any_request(reachable):
    ssh_run, ssh_live, _ = reachable
    ssh_run.return_value = _read(returncode=255)
    result = _run()
    assert result.exit_code == 1
    assert not any("certonly" in c.args[2] for c in ssh_live.call_args_list)


def test_a_dry_run_simulates_the_real_request(reachable):
    """Held names are asked for too, and nothing on the server changes."""
    ssh_run, ssh_live, nginx = reachable
    ssh_run.return_value = _read(LISTING_5.replace("www.example.com", "mcp.example.com www.example.com"))
    with (
        patch("phoxtail.cli.server.ssl.scp_to") as scp,
        patch("phoxtail.cli.server.ssl._install_renewal_cron") as cron,
    ):
        result = _run("--dry-run", resolves=("example.com", "mcp.example.com"))
    assert result.exit_code == 0, result.output
    assert "--dry-run" in _certbot(ssh_live)
    assert _requested(ssh_live) == ["example.com", "mcp.example.com", "www.example.com"]
    nginx.assert_not_called()
    scp.assert_not_called()
    cron.assert_not_called()


@pytest.mark.parametrize(("choice", "served"), [("--www", True), ("--no-www", False)])
def test_skipping_dns_takes_the_explicit_choice_without_lookups(reachable, choice, served):
    _, ssh_live, nginx = reachable
    with patch("phoxtail.cli.server.ssl._dns_resolves_to") as lookup:
        result = CliRunner().invoke(
            app, [IP, "--domain", "example.com", "--email", "ops@example.com", "--skip-dns-check", choice]
        )
    assert result.exit_code == 0, result.output
    lookup.assert_not_called()
    assert ("www.example.com" in _requested(ssh_live)) is served
    assert _nginx_www(nginx) is served
