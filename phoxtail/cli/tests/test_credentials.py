"""Tests for the shared credential resolver."""

from __future__ import annotations

import importlib
import os
import stat

import pytest


@pytest.fixture
def creds(tmp_path, monkeypatch):
    """Isolate ~/.phoxtail to a temp HOME and reload the module.

    The module computes ``CREDENTIALS_DIR`` at import time from
    ``Path.home()``, so we reload it under the patched HOME.
    """
    monkeypatch.setenv("HOME", str(tmp_path))
    from phoxtail.cli.utils import credentials as mod

    importlib.reload(mod)
    assert mod.CREDENTIALS_DIR == tmp_path / ".phoxtail"
    yield mod
    importlib.reload(mod)


def test_host_for_url_variants(creds):
    assert creds.host_for_url("http://localhost") == "localhost"
    assert creds.host_for_url("http://localhost:8000") == "localhost:8000"
    assert creds.host_for_url("https://studio.example.com/") == "studio.example.com"
    assert creds.host_for_url("studio.example.com") == "studio.example.com"
    assert creds.host_for_url("") == "localhost"


def test_resolve_from_file(creds):
    creds.save_token("localhost", "phxt_filetoken")
    assert creds.resolve_token("http://localhost") == "phxt_filetoken"


def test_resolve_other_host_returns_none(creds):
    creds.save_token("localhost", "phxt_x")
    assert creds.resolve_token("http://other.example.com") is None


def test_resolve_missing(creds):
    assert creds.resolve_token("http://localhost") is None


def test_save_then_delete_roundtrip(creds):
    creds.save_token("a.example.com", "phxt_a")
    creds.save_token("b.example.com", "phxt_b")
    assert set(creds.list_hosts()) == {"a.example.com", "b.example.com"}
    assert creds.delete_token("a.example.com") is True
    assert creds.list_hosts() == ["b.example.com"]
    assert creds.delete_token("a.example.com") is False


def test_file_permissions_are_tight(creds):
    creds.save_token("localhost", "phxt_x")
    mode = stat.S_IMODE(os.stat(creds.CREDENTIALS_FILE).st_mode)
    assert mode == 0o600
    dir_mode = stat.S_IMODE(os.stat(creds.CREDENTIALS_DIR).st_mode)
    assert dir_mode == 0o700


def test_malformed_file_is_ignored(creds):
    creds.CREDENTIALS_DIR.mkdir(parents=True, exist_ok=True)
    creds.CREDENTIALS_FILE.write_text("this is not = valid toml [[")
    assert creds.resolve_token("http://localhost") is None
    assert creds.list_hosts() == []
