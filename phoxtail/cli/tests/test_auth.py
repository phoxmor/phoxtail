"""Tests for the ``phoxtail auth`` command group."""

from __future__ import annotations

import importlib

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
