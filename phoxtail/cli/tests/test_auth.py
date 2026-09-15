"""Tests for the ``phoxtail auth`` command group."""

from __future__ import annotations

import importlib
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

from phoxtail.cli import auth
from phoxtail.cli.utils.config import load_config

runner = CliRunner()


@pytest.fixture
def isolated_home(tmp_path, monkeypatch):
    """Route ~/.phoxtail at a temp HOME and reload credentials."""
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    from phoxtail.cli.utils import credentials as mod

    importlib.reload(mod)
    # auth.py imported `credentials` at module load; re-bind so the
    # command reads the reloaded paths.
    importlib.reload(auth)
    yield
    importlib.reload(mod)
    importlib.reload(auth)


def _write_toml(path, api_url: str | None) -> None:
    body = '[project]\nname = "phoxtail"\n'
    if api_url is not None:
        body += f'\n[studio]\napi_url = "{api_url}"\n'
    path.write_text(body)
    load_config.cache_clear()


def test_status_shows_current_host_when_empty(isolated_home, tmp_path):
    """Regression: status used to return early with no stored tokens,
    hiding the project's expected host key. That is the moment the user
    most needs it."""
    _write_toml(tmp_path / "phoxtail.toml", "http://localhost:8080")

    result = runner.invoke(auth.app, ["status"])

    assert result.exit_code == 0
    assert "No tokens stored" in result.stdout
    assert "Current project host:" in result.stdout
    assert "localhost:8080" in result.stdout


def test_status_lists_stored_hosts_and_current(isolated_home, tmp_path):
    _write_toml(tmp_path / "phoxtail.toml", "http://localhost:8080")
    from phoxtail.cli.utils import credentials as mod

    mod.save_token("localhost:8080", "phxt_abc12345EXAMPLEtail")

    result = runner.invoke(auth.app, ["status"])

    assert result.exit_code == 0
    assert "localhost:8080" in result.stdout
    assert "Current project host:" in result.stdout


class TestLoginVerifies:
    """What ``login`` asks the API before it stores a token.

    The question is whether the credential is real, and only
    ``/api/whoami/`` answers that alone. Every other endpoint also asks
    whether the credential may do that particular thing, so a token
    scoped away from it is refused while being perfectly healthy — which
    is what happened when this probe called a streams endpoint and every
    narrowly-scoped key was reported as suspect on the way in.

    That path is asserted rather than left to review because nothing in
    the code's shape distinguishes a right endpoint from a wrong one: the
    old call was ordinary-looking and correct for years, until the API
    grew per-endpoint permissions underneath it.
    """

    @pytest.fixture
    def seen(self, monkeypatch):
        """The requests login made, with a scripted status for each."""
        calls = []
        status = {"code": 200}

        class _Response:
            def __init__(self, url):
                self.status_code = status["code"]
                self.url = url

        def fake_get(url, **kwargs):
            calls.append((url, kwargs.get("headers", {})))
            return _Response(url)

        monkeypatch.setattr(auth.httpx, "get", fake_get)
        return SimpleNamespace(calls=calls, status=status)

    def test_it_asks_whoami_and_nothing_else(self, isolated_home, tmp_path, seen):
        _write_toml(tmp_path / "phoxtail.toml", "http://localhost:8080")

        result = runner.invoke(auth.app, ["login", "--token", "phxt_key"])

        assert result.exit_code == 0
        assert len(seen.calls) == 1
        url, headers = seen.calls[0]
        assert url == "http://localhost:8080/api/whoami/"
        assert headers["Authorization"] == "Bearer phxt_key"

    def test_a_narrow_key_is_saved_without_a_warning(self, isolated_home, tmp_path, seen):
        """The regression this endpoint change exists for.

        A key scoped to one permission is a normal key. Reaching
        ``/whoami/`` is the whole of what login needs from it.
        """
        _write_toml(tmp_path / "phoxtail.toml", "http://localhost:8080")

        result = runner.invoke(auth.app, ["login", "--token", "phxt_narrow"])

        assert "Warning" not in result.stdout
        assert "Saved token" in result.stdout

    def test_a_rejected_key_is_not_saved(self, isolated_home, tmp_path, seen):
        """401 is the one answer that means the token itself is wrong."""
        _write_toml(tmp_path / "phoxtail.toml", "http://localhost:8080")
        seen.status["code"] = 401

        result = runner.invoke(auth.app, ["login", "--token", "phxt_bad"])

        assert result.exit_code == 1
        assert "Not saved" in result.stdout
        from phoxtail.cli.utils import credentials as mod

        assert mod.get_entry("localhost:8080") is None

    def test_an_unreachable_project_still_saves(self, isolated_home, tmp_path, seen):
        """A 502 is about the project, not the credential.

        Refusing to store the token would leave the operator with nothing
        to retry with once the site is back up.
        """
        _write_toml(tmp_path / "phoxtail.toml", "http://localhost:8080")
        seen.status["code"] = 502

        result = runner.invoke(auth.app, ["login", "--token", "phxt_key"])

        assert result.exit_code == 0
        assert "Saving anyway" in result.stdout
        assert "Saved token" in result.stdout

    def test_an_explicit_host_is_the_one_asked(self, isolated_home, tmp_path, seen):
        """``--host`` is the only path where the URL is not the project's.

        It is also the path that bypasses the config entirely, so a
        malformed join here would go unnoticed by every other test.
        """
        _write_toml(tmp_path / "phoxtail.toml", "http://localhost:8080")

        result = runner.invoke(auth.app, ["login", "--token", "phxt_key", "--host", "example.test"])

        assert result.exit_code == 0
        assert seen.calls[0][0] == "http://example.test/api/whoami/"

    def test_an_unreachable_host_still_saves(self, isolated_home, tmp_path, monkeypatch):
        """The branch that fires when the site is down, rather than slow.

        A refused connection raises where a 502 returns, so the two
        reach the same decision by different routes and only one of them
        is covered by the status-code tests.
        """
        _write_toml(tmp_path / "phoxtail.toml", "http://localhost:8080")

        def refuse(url, **kwargs):
            raise auth.httpx.ConnectError("nothing listening")

        monkeypatch.setattr(auth.httpx, "get", refuse)

        result = runner.invoke(auth.app, ["login", "--token", "phxt_key"])

        assert result.exit_code == 0
        assert "could not verify token" in result.stdout
        assert "Saved token" in result.stdout

    def test_no_verify_asks_nothing(self, isolated_home, tmp_path, seen):
        _write_toml(tmp_path / "phoxtail.toml", "http://localhost:8080")

        result = runner.invoke(auth.app, ["login", "--token", "phxt_key", "--no-verify"])

        assert result.exit_code == 0
        assert seen.calls == []
