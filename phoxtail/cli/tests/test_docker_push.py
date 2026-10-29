"""A push refuses an image that carries secrets or user data."""

import subprocess

import pytest
from typer.testing import CliRunner

from phoxtail.cli import docker
from phoxtail.cli.docker import _private_paths, _push_image
from phoxtail.cli.utils.config import load_config


class FakeDocker:
    """Answers `docker run … find` with a canned listing and records pushes."""

    def __init__(self, listing: str | dict[str, str] = "", returncode: int = 0, stderr: str = ""):
        # A str answers every image; a dict answers per image.
        self.listing = listing
        self.returncode = returncode
        self.stderr = stderr
        self.runs: list[list[str]] = []
        self.pushed: list[str] = []

    def run(self, cmd, **kwargs):
        self.runs.append(cmd)
        listing = self.listing if isinstance(self.listing, str) else self.listing[cmd[cmd.index("find") + 1]]
        return subprocess.CompletedProcess(cmd, self.returncode, listing, self.stderr)

    def call(self, cmd, **kwargs):
        assert cmd[:2] == ["docker", "push"]
        self.pushed.append(cmd[2])
        return 0


@pytest.fixture
def fake(monkeypatch):
    def install(**kwargs) -> FakeDocker:
        fake = FakeDocker(**kwargs)
        monkeypatch.setattr(docker.subprocess, "run", fake.run)
        monkeypatch.setattr(docker.subprocess, "call", fake.call)
        return fake

    return install


class TestPrivatePaths:
    def test_searches_app_for_every_private_name_offline_and_locally(self, fake):
        docker_ = fake()
        _private_paths("ghcr.io/acme/site:latest")
        cmd = docker_.runs[0]
        assert cmd[:11] == [
            "docker",
            "run",
            "--rm",
            "--pull",
            "never",
            "--network",
            "none",
            "--user",
            "0",
            "--entrypoint",
            "find",
        ]
        assert cmd[11:13] == ["ghcr.io/acme/site:latest", "/app"]
        names = [cmd[i + 1] for i, arg in enumerate(cmd) if arg == "-name"]
        assert names == [".env", ".env.*", ".phoxtail", "*.sql"]

    def test_lists_what_find_prints(self, fake):
        fake(listing="/app/.phoxtail\n/app/src/.env\n")
        assert _private_paths("img") == ["/app/.phoxtail", "/app/src/.env"]

    def test_a_clean_image_lists_nothing(self, fake):
        fake()
        assert _private_paths("img") == []

    def test_an_image_that_cannot_be_inspected_reads_as_none(self, fake):
        fake(returncode=125, stderr="Unable to find image")
        assert _private_paths("img") is None


class TestPushImage:
    def test_a_clean_image_pushes_both_tags(self, fake):
        docker_ = fake()
        assert _push_image("ghcr.io/acme/site", "abc1234") == 0
        assert docker_.pushed == ["ghcr.io/acme/site:latest", "ghcr.io/acme/site:abc1234"]

    def test_secret_files_refuse_the_push_and_name_the_paths(self, fake, capsys):
        docker_ = fake(listing="/app/.phoxtail\n")
        assert _push_image("ghcr.io/acme/site", "abc1234") == 1
        assert docker_.pushed == []
        out = capsys.readouterr().out
        assert "/app/.phoxtail" in out
        assert "phoxtail docker create dockerignore --force" in out

    def test_one_leaking_tag_stops_every_push(self, fake):
        docker_ = fake(listing={"ghcr.io/acme/site:latest": "", "ghcr.io/acme/site:abc1234": "/app/.env\n"})
        assert _push_image("ghcr.io/acme/site", "abc1234") == 1
        assert docker_.pushed == []

    def test_an_uninspectable_image_refuses_the_push(self, fake):
        docker_ = fake(returncode=125)
        assert _push_image("ghcr.io/acme/site", None) == 1
        assert docker_.pushed == []


class TestPushCommand:
    def test_refuses_a_leaking_image_end_to_end(self, fake, project_dir, monkeypatch):
        (project_dir / "phoxtail.toml").write_text('[project]\nname = "site"\n\n[docker]\nregistry = "ghcr.io/acme"\n')
        load_config.cache_clear()
        monkeypatch.setattr(docker, "_git_sha", lambda: None)
        docker_ = fake(listing="/app/.phoxtail\n")
        result = CliRunner().invoke(docker.app, ["push"])
        assert result.exit_code == 1
        assert docker_.pushed == []
        assert "/app/.phoxtail" in result.output
