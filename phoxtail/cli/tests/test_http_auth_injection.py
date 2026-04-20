"""The CLI HTTP client must inject the bearer token resolved from credentials.

The MCP client (``phoxtail.mcp._http``) uses the exact same resolver and
injection pattern; its integration tests live in ``test_studio_mcp.py``
alongside the tool-level tests.
"""

from __future__ import annotations

import httpx
import pytest


@pytest.fixture(autouse=True)
def isolate_home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("PHOXTAIL_API_TOKEN", raising=False)
    import importlib

    from phoxtail.cli.utils import credentials as mod

    importlib.reload(mod)
    yield
    importlib.reload(mod)


def test_cli_client_injects_bearer_from_env(monkeypatch):
    monkeypatch.setenv("PHOXTAIL_API_TOKEN", "phxt_testtoken")
    from phoxtail.cli.studio import client

    captured: dict = {}

    def fake_request(method, url, **kwargs):
        captured["headers"] = kwargs.get("headers") or {}
        return httpx.Response(200, request=httpx.Request(method, url))

    monkeypatch.setattr(httpx, "request", fake_request)
    client.request("GET", "/blocks/")
    assert captured["headers"].get("Authorization") == "Bearer phxt_testtoken"


def test_cli_client_preserves_explicit_auth_header(monkeypatch):
    monkeypatch.setenv("PHOXTAIL_API_TOKEN", "phxt_env")
    from phoxtail.cli.studio import client

    captured: dict = {}

    def fake_request(method, url, **kwargs):
        captured["headers"] = kwargs.get("headers") or {}
        return httpx.Response(200, request=httpx.Request(method, url))

    monkeypatch.setattr(httpx, "request", fake_request)
    client.request("GET", "/blocks/", headers={"Authorization": "Bearer override"})
    assert captured["headers"].get("Authorization") == "Bearer override"


def test_cli_client_omits_header_when_no_token(monkeypatch):
    from phoxtail.cli.studio import client

    captured: dict = {}

    def fake_request(method, url, **kwargs):
        captured["headers"] = kwargs.get("headers")
        return httpx.Response(200, request=httpx.Request(method, url))

    monkeypatch.setattr(httpx, "request", fake_request)
    client.request("GET", "/blocks/")
    headers = captured["headers"] or {}
    assert "Authorization" not in headers
