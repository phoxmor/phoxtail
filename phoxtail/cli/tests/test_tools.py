"""Tests for the program checks, and for commands meeting a missing program.

Every test here looks programs up for real (``real_programs``), against a
``PATH`` holding only the small fake programs it installs: the lookup under
test is ``shutil.which`` itself, so mocking it would test nothing.
"""

import sys
from unittest.mock import patch

import pytest
import typer
from typer.testing import CliRunner

from phoxtail.__main__ import app
from phoxtail.cli import docker
from phoxtail.cli.utils import tools
from phoxtail.cli.utils.config import load_config
from phoxtail.cli.utils.sources import parse_source, preflight

pytestmark = [
    pytest.mark.real_programs,
    pytest.mark.skipif(sys.platform == "win32", reason="the fake programs are shell scripts"),
]

runner = CliRunner()

DOCKER_OK = """
case "$1 $2" in
  "compose version") echo 2.29.7 ;;
  "info --format") echo 28.1.1 ;;
esac
"""

DAEMON_DOWN = """
case "$1 $2" in
  "compose version") echo 2.29.7 ;;
  "info --format")
    echo "Cannot connect to the Docker daemon at unix:///var/run/docker.sock." >&2
    exit 1 ;;
esac
"""

# Docker with only the old standalone docker-compose beside it: the
# `compose` subcommand does not exist.
NO_COMPOSE_PLUGIN = """
if [ "$1" = compose ]; then
  echo "docker: 'compose' is not a docker command." >&2
  exit 1
fi
"""


@pytest.fixture
def install(tmp_path, monkeypatch):
    """Make PATH hold only the fake programs a test installs."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    monkeypatch.setenv("PATH", str(bin_dir))

    def _install(name: str, script: str = "") -> None:
        program = bin_dir / name
        program.write_text(f"#!/bin/sh\n{script}\nexit 0\n")
        program.chmod(0o755)

    return _install


class TestCheck:
    def test_installed_program_is_no_problem(self, install):
        install("uv")
        assert tools.check(tools.UV) is None

    def test_missing_program_names_itself_and_how_to_install_it(self, install):
        problem = tools.check(tools.UV)
        assert problem is not None
        assert problem.reason == "uv not found"
        assert "astral.sh/uv" in problem.remedy

    def test_first_missing_program_is_the_one_reported(self, install):
        install("ssh")
        problem = tools.check(tools.SSH, tools.SCP, tools.RSYNC)
        assert problem is not None
        assert problem.reason == "scp not found"

    def test_compose_without_docker_reports_docker(self, install):
        problem = tools.check(tools.COMPOSE)
        assert problem is not None
        assert problem.reason == "Docker not found"
        assert "docs.docker.com" in problem.remedy

    def test_compose_needs_the_v2_plugin(self, install):
        install("docker", NO_COMPOSE_PLUGIN)
        install("docker-compose")
        problem = tools.check(tools.COMPOSE)
        assert problem is not None
        assert problem.reason == "Docker Compose v2 not found"

    def test_compose_failure_carries_dockers_own_words(self, install):
        """A broken docker context fails `docker compose` too; reinstalling would not help."""
        install("docker", 'echo "context \\"gone\\": context not found" >&2; exit 1')
        problem = tools.check(tools.COMPOSE)
        assert problem is not None
        assert 'Docker said: context "gone": context not found' in problem.remedy

    def test_compose_plugin_present(self, install):
        install("docker", DOCKER_OK)
        assert tools.check(tools.COMPOSE) is None

    def test_daemon_is_only_asked_when_requested(self, install):
        install("docker", DAEMON_DOWN)
        assert tools.check(tools.COMPOSE) is None

    def test_daemon_down_carries_dockers_own_words(self, install):
        install("docker", DAEMON_DOWN)
        problem = tools.check(tools.COMPOSE, daemon=True)
        assert problem is not None
        assert problem.reason == "Docker is not running, or this user may not use it"
        assert "Docker said: Cannot connect to the Docker daemon" in problem.remedy

    def test_daemon_answering(self, install):
        install("docker", DOCKER_OK)
        assert tools.check(tools.COMPOSE, daemon=True) is None

    def test_daemon_that_names_no_version_has_not_answered(self, install):
        install("docker", 'case "$1 $2" in "compose version") echo 2.29.7 ;; esac')
        problem = tools.check(tools.COMPOSE, daemon=True)
        assert problem is not None
        assert problem.reason == "Docker is not running, or this user may not use it"

    def test_daemon_that_never_answers_is_reported_not_waited_on(self, install, monkeypatch):
        monkeypatch.setattr(tools, "DAEMON_TIMEOUT", 0.5)
        install("docker", 'if [ "$1" = info ]; then exec /bin/sleep 5; fi')
        problem = tools.check(tools.DOCKER, daemon=True)
        assert problem is not None
        assert problem.reason == "Docker did not answer"

    def test_daemon_without_docker_reports_docker(self, install):
        problem = tools.check(daemon=True)
        assert problem is not None
        assert problem.reason == "Docker not found"

    @pytest.mark.parametrize(
        ("platform", "hint"),
        [("linux", "systemctl start docker"), ("darwin", "Start Docker Desktop")],
    )
    def test_start_hint_follows_the_platform(self, install, monkeypatch, platform, hint):
        install("docker", DAEMON_DOWN)
        monkeypatch.setattr(tools.sys, "platform", platform)
        problem = tools.check(tools.DOCKER, daemon=True)
        assert problem is not None
        assert hint in problem.remedy

    def test_docker_group_hint_is_linux_only(self, install, monkeypatch):
        install("docker", DAEMON_DOWN)
        monkeypatch.setattr(tools.sys, "platform", "darwin")
        problem = tools.check(tools.DOCKER, daemon=True)
        assert problem is not None
        assert "docker group" not in problem.remedy


class TestComposeVersion:
    def test_reads_the_plugin_version(self, install):
        install("docker", DOCKER_OK)
        assert tools.compose_version() == "2.29.7"

    def test_no_docker_is_no_version(self, install):
        assert tools.compose_version() is None

    def test_no_plugin_is_no_version(self, install):
        install("docker", NO_COMPOSE_PLUGIN)
        assert tools.compose_version() is None


class TestRequire:
    def test_exits_with_the_reason_and_the_remedy(self, install, capsys):
        with pytest.raises(typer.Exit) as exc:
            tools.require(tools.GIT, note="Or carry on without it.")
        assert exc.value.exit_code == 1
        out = capsys.readouterr().out
        assert "Error: git not found." in out
        assert "git-scm.com" in out
        assert "Or carry on without it." in out

    def test_installed_program_passes(self, install):
        install("git")
        tools.require(tools.GIT)


class TestCommandsMeetingAMissingProgram:
    """A command checks before its first side effect, and says what is missing."""

    def test_docker_up_never_runs_without_docker(self, install):
        with patch("phoxtail.cli.docker.subprocess.call") as call:
            result = runner.invoke(app, ["docker", "up"])
        assert result.exit_code == 1
        assert "Docker not found" in result.output
        call.assert_not_called()

    def test_test_offers_the_cli_tests_instead(self, install):
        result = runner.invoke(app, ["test"])
        assert result.exit_code == 1
        assert "phoxtail test --cli" in result.output

    def test_net_status_reports_docker_rather_than_crashing(self, install):
        result = runner.invoke(app, ["net", "status"])
        assert result.exit_code == 0
        assert "unknown (Docker not found)" in result.output

    def test_db_pull_stops_before_reaching_the_server(self, install):
        install("ssh")
        install("scp")
        with patch("phoxtail.cli.db.verify_server_identity") as verify:
            result = runner.invoke(app, ["db", "pull", "203.0.113.5"])
        assert result.exit_code == 1
        assert "Docker not found" in result.output
        verify.assert_not_called()

    def test_media_pull_needs_rsync(self, install):
        install("ssh")
        with patch("phoxtail.cli.media.verify_server_identity") as verify:
            result = runner.invoke(app, ["media", "pull", "203.0.113.5"])
        assert result.exit_code == 1
        assert "rsync not found" in result.output
        verify.assert_not_called()

    def test_compose_file_is_written_without_uv(self, install, project_dir):
        (project_dir / ".venv").mkdir()
        result = runner.invoke(
            app, ["docker", "create", "compose", "development", "-p", "demo", "--postgres-version", "18"]
        )
        assert result.exit_code == 0, result.output
        assert "uv not found — fragments may be stale" in result.output
        assert (project_dir / "docker-compose.yaml").exists()

    def test_images_are_tagged_latest_only_without_git(self, install, project_dir, capsys):
        (project_dir / "phoxtail.toml").write_text('[project]\nname = "demo"\n\n[docker]\nregistry = "ghcr.io/acme"\n')
        load_config.cache_clear()
        assert docker._registry_and_sha() == ("ghcr.io/acme/demo", None)
        out = capsys.readouterr().out
        assert "git not found" in out
        assert "Install git" in out

    def test_git_source_without_git_fails_its_preflight(self, install):
        reachable, why = preflight(parse_source("git+https://github.com/acme/widget.git"), "widget")
        assert reachable is False
        assert "git not found" in why
