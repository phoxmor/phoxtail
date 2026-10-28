"""Tests for cli.db commands."""

import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import pytest
import typer
from typer.testing import CliRunner

from phoxtail.cli.db import PG_DUMP, _dump_into, app, backup, backup_name, pull, restore

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _completed(returncode=0, stdout="", stderr=""):
    return subprocess.CompletedProcess([], returncode, stdout=stdout, stderr=stderr)


# ---------------------------------------------------------------------------
# pull
# ---------------------------------------------------------------------------


def _pull():
    return pull(ip="203.0.113.5", user="phoxtail")


class TestPull:
    """Tests for the db pull command.

    Every test patches ``verify_server_identity`` (network) and
    ``Confirm.ask`` (interactive gate) so ``pull`` runs through.
    """

    @patch("phoxtail.cli.db.Confirm.ask", return_value=True)
    @patch("phoxtail.cli.db.verify_server_identity")
    @patch("phoxtail.cli.db.docker_manage")
    @patch("phoxtail.cli.db.docker_db")
    @patch("phoxtail.cli.db.read_env_value", return_value="localhost")
    @patch("phoxtail.cli.db.subprocess.run")
    @patch("phoxtail.cli.db.typer.prompt", return_value="secret")
    def test_happy_path_with_superusers(
        self, mock_prompt, mock_run, mock_env, mock_docker_db, mock_manage, mock_verify, mock_confirm, project_dir
    ):
        """Full pull: dump, download, backup, restore, hostnames, passwords."""
        mock_run.return_value = _completed()

        # docker_manage for superuser discovery
        mock_manage.return_value = _completed(stdout="some noise\n__SUPERUSERS__:admin@test.com,editor@test.com")

        backups_dir = project_dir / "db-backups"
        dump_path = backups_dir / "remote_pull.sql"

        # Create the dump file so the restore step can open it
        backups_dir.mkdir()
        dump_path.write_text("-- SQL dump")

        _pull()

        # Server identity was checked before anything ran
        mock_verify.assert_called_once_with("phoxtail", "203.0.113.5")

        # SSH dump command
        ssh_call = mock_run.call_args_list[0]
        assert ssh_call[0][0][0] == "ssh"
        assert "pg_dump" in ssh_call[0][0][-1]

        # SCP download
        scp_call = mock_run.call_args_list[1]
        assert scp_call[0][0][0] == "scp"

        # Remote cleanup
        cleanup_call = mock_run.call_args_list[2]
        assert "rm -f" in cleanup_call[0][0][-1]

        # Restore via stdin
        restore_call = mock_run.call_args_list[3]
        restore_args = " ".join(restore_call[0][0])
        assert "DROP SCHEMA public CASCADE" in restore_args

        # Hostname update
        hostname_calls = [c for c in mock_docker_db.call_args_list if "UPDATE wagtailcore_site" in str(c)]
        assert len(hostname_calls) == 1

        # Password reset prompt was called
        mock_prompt.assert_called_once()

        # Dump file cleaned up
        assert not dump_path.exists()

    @patch("phoxtail.cli.db.Confirm.ask", return_value=False)
    @patch("phoxtail.cli.db.verify_server_identity")
    @patch("phoxtail.cli.db.subprocess.run")
    def test_declining_confirmation_aborts(self, mock_run, mock_verify, mock_confirm, project_dir):
        """Answering no at the confirmation gate exits cleanly, touching nothing."""
        with pytest.raises(typer.Exit) as exc_info:
            _pull()
        assert exc_info.value.exit_code == 0
        mock_run.assert_not_called()

    @patch("phoxtail.cli.db.Confirm.ask", return_value=True)
    @patch("phoxtail.cli.db.verify_server_identity")
    @patch("phoxtail.cli.db.docker_manage")
    @patch("phoxtail.cli.db.docker_db")
    @patch("phoxtail.cli.db.read_env_value", return_value="localhost")
    @patch("phoxtail.cli.db.subprocess.run")
    def test_no_superusers_found(
        self, mock_run, mock_env, mock_docker_db, mock_manage, mock_verify, mock_confirm, project_dir
    ):
        """When no superusers exist, skip password prompt."""
        mock_run.return_value = _completed()
        mock_manage.return_value = _completed(stdout="__SUPERUSERS__:")

        backups_dir = project_dir / "db-backups"
        backups_dir.mkdir()
        (backups_dir / "remote_pull.sql").write_text("-- SQL")

        _pull()

        # No prompt should have been triggered (would error if typer.prompt called)

    @patch("phoxtail.cli.db.Confirm.ask", return_value=True)
    @patch("phoxtail.cli.db.verify_server_identity")
    @patch("phoxtail.cli.db.docker_manage")
    @patch("phoxtail.cli.db.docker_db")
    @patch("phoxtail.cli.db.read_env_value", return_value=None)
    @patch("phoxtail.cli.db.subprocess.run")
    def test_domain_defaults_to_localhost(
        self, mock_run, mock_env, mock_docker_db, mock_manage, mock_verify, mock_confirm, project_dir
    ):
        """When DOMAIN env var is unset, defaults to 'localhost'."""
        mock_run.return_value = _completed()
        mock_manage.return_value = _completed(stdout="__SUPERUSERS__:")

        backups_dir = project_dir / "db-backups"
        backups_dir.mkdir()
        (backups_dir / "remote_pull.sql").write_text("-- SQL")

        _pull()

        # Hostname update should use 'localhost'
        hostname_call = [c for c in mock_docker_db.call_args_list if "UPDATE wagtailcore_site" in str(c)]
        assert len(hostname_call) == 1
        assert "localhost" in str(hostname_call[0])

    @patch("phoxtail.cli.db.Confirm.ask", return_value=True)
    @patch("phoxtail.cli.db.verify_server_identity")
    @patch("phoxtail.cli.db.docker_db")
    @patch("phoxtail.cli.db.read_env_value", return_value="localhost")
    @patch("phoxtail.cli.db.subprocess.run")
    def test_ssh_failure_exits(self, mock_run, mock_env, mock_docker_db, mock_verify, mock_confirm, project_dir):
        """SSH failure raises typer.Exit."""
        mock_run.side_effect = subprocess.CalledProcessError(1, "ssh", stderr="Connection refused")

        with pytest.raises(typer.Exit):
            _pull()

    @patch("phoxtail.cli.db.Confirm.ask", return_value=True)
    @patch("phoxtail.cli.db.verify_server_identity")
    @patch("phoxtail.cli.db.docker_manage")
    @patch("phoxtail.cli.db.docker_db")
    @patch("phoxtail.cli.db.read_env_value", return_value="localhost")
    @patch("phoxtail.cli.db.subprocess.run")
    def test_safety_backup_failure_non_fatal(
        self, mock_run, mock_env, mock_docker_db, mock_manage, mock_verify, mock_confirm, project_dir
    ):
        """Safety backup failure doesn't abort the pull."""
        mock_run.return_value = _completed()
        mock_manage.return_value = _completed(stdout="__SUPERUSERS__:")

        # Safety backup fails
        mock_docker_db.side_effect = [
            subprocess.CalledProcessError(1, "pg_dump"),  # safety backup
            _completed(),  # hostname update
        ]

        backups_dir = project_dir / "db-backups"
        backups_dir.mkdir()
        (backups_dir / "remote_pull.sql").write_text("-- SQL")

        # Should not raise
        _pull()

    @patch("phoxtail.cli.db.Confirm.ask", return_value=True)
    @patch("phoxtail.cli.db.verify_server_identity")
    @patch("phoxtail.cli.db.docker_db")
    @patch("phoxtail.cli.db.read_env_value", return_value="localhost")
    @patch("phoxtail.cli.db.subprocess.run")
    def test_restore_failure_exits(self, mock_run, mock_env, mock_docker_db, mock_verify, mock_confirm, project_dir):
        """Restore failure raises typer.Exit."""
        # SSH + SCP + cleanup succeed, restore fails
        mock_run.side_effect = [
            _completed(),  # ssh dump
            _completed(),  # scp download
            _completed(),  # remote cleanup
            _completed(returncode=1, stderr="restore error"),  # restore
        ]

        backups_dir = project_dir / "db-backups"
        backups_dir.mkdir()
        (backups_dir / "remote_pull.sql").write_text("-- SQL")

        with pytest.raises(typer.Exit):
            _pull()

    @patch("phoxtail.cli.db.Confirm.ask", return_value=True)
    @patch("phoxtail.cli.db.verify_server_identity")
    @patch("phoxtail.cli.db.docker_db")
    @patch("phoxtail.cli.db.read_env_value", return_value="localhost")
    @patch("phoxtail.cli.db.subprocess.run")
    def test_dump_cleanup_on_failure(self, mock_run, mock_env, mock_docker_db, mock_verify, mock_confirm, project_dir):
        """Dump file is cleaned up even when pull fails."""
        mock_run.side_effect = [
            _completed(),  # ssh dump
            _completed(),  # scp download
            _completed(),  # remote cleanup
            _completed(returncode=1, stderr="error"),  # restore
        ]

        backups_dir = project_dir / "db-backups"
        backups_dir.mkdir()
        dump_path = backups_dir / "remote_pull.sql"
        dump_path.write_text("-- SQL")

        with pytest.raises(typer.Exit):
            _pull()

        assert not dump_path.exists()

    @patch("phoxtail.cli.db.Confirm.ask", return_value=True)
    @patch("phoxtail.cli.db.verify_server_identity")
    @patch("phoxtail.cli.db.docker_manage")
    @patch("phoxtail.cli.db.docker_db")
    @patch("phoxtail.cli.db.read_env_value", return_value="mysite.local")
    @patch("phoxtail.cli.db.subprocess.run")
    def test_custom_domain(
        self, mock_run, mock_env, mock_docker_db, mock_manage, mock_verify, mock_confirm, project_dir
    ):
        """Custom DOMAIN value is used for hostname update."""
        mock_run.return_value = _completed()
        mock_manage.return_value = _completed(stdout="__SUPERUSERS__:")

        backups_dir = project_dir / "db-backups"
        backups_dir.mkdir()
        (backups_dir / "remote_pull.sql").write_text("-- SQL")

        _pull()

        hostname_call = [c for c in mock_docker_db.call_args_list if "UPDATE wagtailcore_site" in str(c)]
        assert "mysite.local" in str(hostname_call[0])

    @patch("phoxtail.cli.db.Confirm.ask", return_value=True)
    @patch("phoxtail.cli.db.verify_server_identity")
    @patch("phoxtail.cli.db.docker_manage")
    @patch("phoxtail.cli.db.docker_db")
    @patch("phoxtail.cli.db.read_env_value", return_value="localhost")
    @patch("phoxtail.cli.db.subprocess.run")
    def test_superuser_marker_ignores_noise(
        self, mock_run, mock_env, mock_docker_db, mock_manage, mock_verify, mock_confirm, project_dir
    ):
        """Superuser parsing ignores Django shell startup noise."""
        mock_run.return_value = _completed()
        mock_manage.return_value = _completed(stdout="Python 3.11.0\nType 'help'...\n__SUPERUSERS__:admin@test.com")

        backups_dir = project_dir / "db-backups"
        backups_dir.mkdir()
        (backups_dir / "remote_pull.sql").write_text("-- SQL")

        with patch("phoxtail.cli.db.typer.prompt", return_value="pw"):
            _pull()

        # Password set command was issued
        assert mock_manage.call_count == 2  # discovery + password set


# ---------------------------------------------------------------------------
# backup
# ---------------------------------------------------------------------------


class TestBackupName:
    """A backup is named after the database it holds, not where it was made."""

    def test_slug_environment_and_utc_time(self):
        name = backup_name("production")
        assert re.fullmatch(r"phoxtail_production_\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}\.sql", name)

    def test_time_is_utc(self):
        frozen = datetime(2026, 10, 28, 10, 19, 28, tzinfo=UTC)
        with patch("phoxtail.cli.db.datetime") as mock_datetime:
            mock_datetime.now.return_value = frozen
            assert backup_name("development") == "phoxtail_development_2026-10-28_10-19-28.sql"
        mock_datetime.now.assert_called_once_with(UTC)

    @pytest.mark.parametrize("environment", [None, ""])
    def test_missing_environment_stops(self, environment):
        with pytest.raises(typer.Exit) as exc_info:
            backup_name(environment)
        assert exc_info.value.exit_code == 1

    @pytest.mark.parametrize("environment", ["prod_eu", "prod eu", "x;rm -rf ~", "../production"])
    def test_environment_that_is_not_a_plain_word_stops(self, environment):
        """It lands in a file name and a remote shell command."""
        with pytest.raises(typer.Exit):
            backup_name(environment)


class TestBackup:
    """Tests for the local db backup."""

    @pytest.fixture
    def env_file(self, project_dir):
        (project_dir / ".env").write_text("DJANGO_ENV=development\n")

    @patch("phoxtail.cli.db.docker_db")
    def test_backup_success(self, mock_docker_db, env_file):
        mock_docker_db.return_value = _completed()
        backup(ip=None)
        mock_docker_db.assert_called_once()
        command = mock_docker_db.call_args[0][0]
        name = re.search(r"phoxtail_development_[\d_-]+\.sql", command)[0]
        assert command == _dump_into(name)


class TestDumpInto:
    """A file under a backup's name is only ever a complete dump."""

    def test_dumps_to_partial_then_renames(self):
        name = "phoxtail_production_2026-10-28_10-19-28.sql"
        partial = f"/db-backups/{name}.partial"
        assert _dump_into(name) == (
            f"{PG_DUMP} > {partial} && test -s {partial} && mv {partial} /db-backups/{name}"
            f" || {{ rm -f {partial}; exit 1; }}"
        )

    @pytest.mark.parametrize(
        ("dump", "leaves"),
        [
            ("echo '-- dump'", ["x.sql"]),  # success: only the named file
            ("true", []),  # empty dump: nothing
            ("{ echo partial; false; }", []),  # wrote data, then failed: nothing
        ],
    )
    def test_shell_behaviour(self, tmp_path, dump, leaves):
        """Run the real shell against a scratch folder standing in for /db-backups."""
        backups = tmp_path / "db-backups"
        backups.mkdir()
        script = _dump_into("x.sql").replace(PG_DUMP, dump).replace("/db-backups", str(backups))
        result = subprocess.run(["sh", "-c", script], capture_output=True)
        assert (result.returncode == 0) == bool(leaves)
        assert sorted(p.name for p in backups.iterdir()) == leaves

    @patch("phoxtail.cli.db.docker_db")
    def test_quoted_environment_is_read(self, mock_docker_db, project_dir):
        (project_dir / ".env").write_text('DJANGO_ENV="development"\n')
        mock_docker_db.return_value = _completed()
        backup(ip=None)
        assert "/db-backups/phoxtail_development_" in mock_docker_db.call_args[0][0]

    @patch("phoxtail.cli.db.docker_db")
    def test_missing_environment_dumps_nothing(self, mock_docker_db, project_dir):
        with pytest.raises(typer.Exit) as exc_info:
            backup(ip=None)
        assert exc_info.value.exit_code == 1
        mock_docker_db.assert_not_called()

    @patch("phoxtail.cli.db.docker_db")
    def test_backup_failure_exits(self, mock_docker_db, env_file):
        mock_docker_db.side_effect = subprocess.CalledProcessError(1, "pg_dump", stderr="no db")
        with pytest.raises(typer.Exit):
            backup(ip=None)


class TestBackupRemote:
    """Tests for db backup <ip>: dump on the server, keep it there, copy it here."""

    IP = "203.0.113.5"

    def _run(self, environment="DJANGO_ENV=production\n", dump=None, download=None):
        """subprocess.run fake: env read, server dump, download, in that order.

        A successful download writes the file scp was told to write.
        """

        def scp(cmd, **kwargs):
            if download is not None:
                Path(cmd[-1]).write_text("-- half a dump")
                return download
            Path(cmd[-1]).write_text("-- dump")
            return _completed()

        steps = iter([lambda cmd, **kw: _completed(stdout=environment), lambda cmd, **kw: dump or _completed(), scp])
        return lambda cmd, **kwargs: next(steps)(cmd, **kwargs)

    @patch("phoxtail.cli.db.verify_server_identity")
    @patch("phoxtail.cli.db.subprocess.run")
    def test_happy_path(self, mock_run, mock_verify, project_dir):
        mock_run.side_effect = self._run()
        backup(ip=self.IP, user="phoxtail")

        mock_verify.assert_called_once_with("phoxtail", self.IP)
        env_call, dump_call, scp_call = (c[0][0] for c in mock_run.call_args_list)

        # The environment comes from the server's own .env.
        assert env_call[0] == "ssh"
        assert env_call[-1] == "grep -m1 '^DJANGO_ENV=' ~/phoxtail/.env"

        # The dump is written into the server's db-backups and checked non-empty.
        assert dump_call[0] == "ssh"
        assert dump_call[-2] == "phoxtail@203.0.113.5"
        name = re.search(r"phoxtail_production_[\d_-]+\.sql", dump_call[-1])[0]
        assert dump_call[-1] == f"cd ~/phoxtail && docker compose exec -T db sh -c '{_dump_into(name)}'"

        # The same file is downloaded under a .partial name, then renamed.
        assert scp_call[0] == "scp"
        assert scp_call[-2] == f"phoxtail@203.0.113.5:~/phoxtail/db-backups/{name}"
        assert scp_call[-1] == str(project_dir / "db-backups" / f"{name}.partial")
        assert sorted(p.name for p in (project_dir / "db-backups").iterdir()) == [name]

        # Nothing is deleted on either side, except a failed dump's .partial.
        removals = re.findall(r"rm -f (\S+);", " ".join(" ".join(c[0][0]) for c in mock_run.call_args_list))
        assert removals == [f"/db-backups/{name}.partial"]

    @patch("phoxtail.cli.db.verify_server_identity")
    @patch("phoxtail.cli.db.subprocess.run")
    def test_environment_is_the_servers_not_the_local_one(self, mock_run, mock_verify, project_dir):
        """A stale local deploy .env must not name the server's backup."""
        (project_dir / ".env").write_text("DJANGO_ENV=development\n")
        deploy = project_dir / ".phoxtail" / "deploy"
        deploy.mkdir(parents=True)
        (deploy / ".env").write_text("DJANGO_ENV=staging\n")
        mock_run.side_effect = self._run(environment="DJANGO_ENV='production'\n")

        backup(ip=self.IP, user="phoxtail")

        assert "/db-backups/phoxtail_production_" in mock_run.call_args_list[1][0][0][-1]

    @patch("phoxtail.cli.db.verify_server_identity")
    @patch("phoxtail.cli.db.subprocess.run")
    def test_custom_user(self, mock_run, mock_verify, project_dir):
        mock_run.side_effect = self._run()
        backup(ip=self.IP, user="deploy")
        mock_verify.assert_called_once_with("deploy", self.IP)
        assert all("deploy@203.0.113.5" in " ".join(c[0][0]) for c in mock_run.call_args_list)

    @patch("phoxtail.cli.db.verify_server_identity")
    @patch("phoxtail.cli.db.subprocess.run")
    def test_missing_server_environment_dumps_nothing(self, mock_run, mock_verify, project_dir):
        mock_run.side_effect = [_completed(returncode=1, stdout="")]
        with pytest.raises(typer.Exit) as exc_info:
            backup(ip=self.IP, user="phoxtail")
        assert exc_info.value.exit_code == 1
        assert mock_run.call_count == 1  # only the env read

    @patch("phoxtail.cli.db.verify_server_identity")
    @patch("phoxtail.cli.db.subprocess.run")
    def test_dump_failure_downloads_nothing(self, mock_run, mock_verify, project_dir):
        mock_run.side_effect = self._run(dump=_completed(returncode=1, stderr="no such service: db"))
        with pytest.raises(typer.Exit) as exc_info:
            backup(ip=self.IP, user="phoxtail")
        assert exc_info.value.exit_code == 1
        assert mock_run.call_count == 2  # no scp

    @patch("phoxtail.cli.db.console.print")
    @patch("phoxtail.cli.db.verify_server_identity")
    @patch("phoxtail.cli.db.subprocess.run")
    def test_download_failure_points_at_the_server_copy(self, mock_run, mock_verify, mock_print, project_dir):
        mock_run.side_effect = self._run(download=_completed(returncode=1, stderr="Permission denied"))
        with pytest.raises(typer.Exit) as exc_info:
            backup(ip=self.IP, user="phoxtail")
        assert exc_info.value.exit_code == 1
        message = mock_print.call_args[0][0]
        assert "Permission denied" in message
        assert "safe on the server: ~/phoxtail/db-backups/phoxtail_production_" in message
        # The half-written download is gone; nothing carries a backup's name.
        assert list((project_dir / "db-backups").iterdir()) == []

    @pytest.mark.parametrize(
        ("returncode", "reason"),
        [(255, "could not reach the server"), (2, "cannot read ~/phoxtail/.env")],
    )
    @patch("phoxtail.cli.db.console.print")
    @patch("phoxtail.cli.db.verify_server_identity")
    @patch("phoxtail.cli.db.subprocess.run")
    def test_environment_read_failure_is_named(
        self, mock_run, mock_verify, mock_print, project_dir, returncode, reason
    ):
        """Not reported as "DJANGO_ENV is not set" when the read itself failed."""
        mock_run.side_effect = [_completed(returncode=returncode, stderr="boom")]
        with pytest.raises(typer.Exit):
            backup(ip=self.IP, user="phoxtail")
        assert mock_print.call_args[0][0] == f"[red]Error:[/red] {reason}: boom"
        assert mock_run.call_count == 1

    @patch("phoxtail.cli.db.subprocess.run")
    @patch("phoxtail.cli.db.verify_server_identity", side_effect=typer.Exit(1))
    def test_wrong_server_touches_nothing(self, mock_verify, mock_run, project_dir):
        with pytest.raises(typer.Exit):
            backup(ip=self.IP, user="phoxtail")
        mock_run.assert_not_called()


class TestBackupCommandLine:
    """Through Typer: the IP is optional and --user defaults to phoxtail."""

    @patch("phoxtail.cli.db._backup_remote")
    @patch("phoxtail.cli.db._backup_local")
    def test_no_ip_backs_up_locally(self, mock_local, mock_remote):
        result = CliRunner().invoke(app, ["backup"])
        assert result.exit_code == 0, result.output
        mock_local.assert_called_once_with()
        mock_remote.assert_not_called()

    @patch("phoxtail.cli.db._backup_remote")
    @patch("phoxtail.cli.db._backup_local")
    def test_ip_backs_up_the_server(self, mock_local, mock_remote):
        result = CliRunner().invoke(app, ["backup", "203.0.113.5"])
        assert result.exit_code == 0, result.output
        mock_remote.assert_called_once_with("203.0.113.5", "phoxtail")
        mock_local.assert_not_called()

    @patch("phoxtail.cli.db._backup_remote")
    def test_user_option(self, mock_remote):
        result = CliRunner().invoke(app, ["backup", "203.0.113.5", "-u", "deploy"])
        assert result.exit_code == 0, result.output
        mock_remote.assert_called_once_with("203.0.113.5", "deploy")


# ---------------------------------------------------------------------------
# restore
# ---------------------------------------------------------------------------


class TestRestore:
    """Tests for the db restore command."""

    @patch("phoxtail.cli.db.docker_db")
    @patch("rich.prompt.Confirm.ask", return_value=True)
    def test_restore_success(self, mock_confirm, mock_docker_db):
        mock_docker_db.return_value = _completed()
        restore(backup_file="2026-03-15_12-00-00.sql")

        assert mock_docker_db.call_count == 2  # safety backup + restore
        # Restore command references the backup file
        restore_call = mock_docker_db.call_args_list[1][0][0]
        assert "2026-03-15_12-00-00.sql" in restore_call

    @patch("phoxtail.cli.db.docker_db")
    @patch("rich.prompt.Confirm.ask", return_value=False)
    def test_restore_cancelled(self, mock_confirm, mock_docker_db):
        with pytest.raises(typer.Exit) as exc_info:
            restore(backup_file="backup.sql")
        assert exc_info.value.exit_code == 0
        mock_docker_db.assert_not_called()

    @patch("phoxtail.cli.db.docker_db")
    @patch("rich.prompt.Confirm.ask", return_value=True)
    def test_restore_failure_exits(self, mock_confirm, mock_docker_db):
        mock_docker_db.side_effect = [
            _completed(),  # safety backup succeeds
            subprocess.CalledProcessError(1, "psql", stderr="restore error"),
        ]
        with pytest.raises(typer.Exit):
            restore(backup_file="backup.sql")
