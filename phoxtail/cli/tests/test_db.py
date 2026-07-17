"""Tests for cli.db commands."""

import subprocess
from unittest.mock import patch

import pytest
import typer

from phoxtail.cli.db import backup, pull, restore

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


class TestBackup:
    """Tests for the db backup command."""

    @patch("phoxtail.cli.db.docker_db")
    def test_backup_success(self, mock_docker_db):
        mock_docker_db.return_value = _completed()
        backup()
        mock_docker_db.assert_called_once()
        assert "pg_dump" in mock_docker_db.call_args[0][0]

    @patch("phoxtail.cli.db.docker_db")
    def test_backup_failure_exits(self, mock_docker_db):
        mock_docker_db.side_effect = subprocess.CalledProcessError(1, "pg_dump", stderr="no db")
        with pytest.raises(typer.Exit):
            backup()


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
