"""Tests for cli.utils.docker."""

import subprocess
from unittest.mock import patch

import pytest

from phoxtail.cli.utils.docker import docker_db, docker_manage


class TestDockerManage:
    @patch("phoxtail.cli.utils.docker.subprocess.run")
    def test_builds_correct_command(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
        docker_manage("migrate", "--no-input")
        cmd = mock_run.call_args[0][0]
        assert cmd == [
            "docker",
            "compose",
            "run",
            "--rm",
            "web",
            "python",
            "manage.py",
            "migrate",
            "--no-input",
        ]

    @patch("phoxtail.cli.utils.docker.subprocess.run")
    def test_raises_on_failure_with_stderr(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="relation does not exist"
        )
        with pytest.raises(subprocess.CalledProcessError) as exc_info:
            docker_manage("loaddata", "fixture.json")
        assert "relation does not exist" in exc_info.value.stderr

    @patch("phoxtail.cli.utils.docker.subprocess.run")
    def test_capture_false_does_not_raise(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="")
        # Should not raise when capture=False
        result = docker_manage("runserver", capture=False)
        assert result.returncode == 1


class TestDockerDb:
    @patch("phoxtail.cli.utils.docker.subprocess.run")
    def test_builds_correct_command(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
        docker_db("pg_dump -h localhost")
        cmd = mock_run.call_args[0][0]
        assert cmd == [
            "docker",
            "compose",
            "exec",
            "db",
            "sh",
            "-c",
            "pg_dump -h localhost",
        ]

    @patch("phoxtail.cli.utils.docker.subprocess.run")
    def test_raises_on_failure_with_stderr(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="connection refused"
        )
        with pytest.raises(subprocess.CalledProcessError) as exc_info:
            docker_db("pg_dump -h localhost")
        assert "connection refused" in exc_info.value.stderr
