"""Credential storage for Phoxtail API access tokens.

A single resolver is shared by the CLI (``phoxtail/cli/studio/client.py``)
and the MCP server (``phoxtail/mcp/_http.py``). The precedence is:

1. ``PHOXTAIL_API_TOKEN`` environment variable.
2. ``~/.phoxtail/credentials`` TOML file, keyed by host.
3. ``None`` — the caller decides how to surface "unauthenticated".

The file format mirrors the convention documented in
``docs/docs/patterns/personal-access-tokens.md``::

    ["localhost"]
    token = "phxt_..."

    ["studio.example.com"]
    token = "phxt_..."

Permissions are set to 0700/0600 on write so a casual ``ls`` of the home
directory does not expose the file to other local users.
"""

from __future__ import annotations

import os
import stat
import tomllib
from pathlib import Path
from urllib.parse import urlparse

CREDENTIALS_DIR = Path.home() / ".phoxtail"
CREDENTIALS_FILE = CREDENTIALS_DIR / "credentials"
ENV_VAR = "PHOXTAIL_API_TOKEN"


def host_for_url(base_url: str) -> str:
    """Derive the host key used to index tokens from an API base URL.

    Accepts values with or without a scheme; returns the lowercased
    netloc (``host[:port]``). Falls back to ``"localhost"`` for empty or
    malformed input so we always have a usable key.
    """
    if not base_url:
        return "localhost"
    url = base_url if "://" in base_url else f"http://{base_url}"
    netloc = urlparse(url).netloc.lower()
    return netloc or "localhost"


def _read_file() -> dict:
    if not CREDENTIALS_FILE.is_file():
        return {}
    try:
        with open(CREDENTIALS_FILE, "rb") as f:
            data = tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError):
        return {}
    return {k: v for k, v in data.items() if isinstance(v, dict)}


def _write_file(data: dict) -> None:
    CREDENTIALS_DIR.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(CREDENTIALS_DIR, stat.S_IRWXU)
    except OSError:
        pass
    lines: list[str] = []
    for host, entry in data.items():
        token = str(entry.get("token", ""))
        safe_host = host.replace('"', '\\"')
        safe_token = token.replace('"', '\\"')
        lines.append(f'["{safe_host}"]\ntoken = "{safe_token}"\n')
    CREDENTIALS_FILE.write_text("\n".join(lines))
    try:
        os.chmod(CREDENTIALS_FILE, stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass


def resolve_token(base_url: str) -> str | None:
    """Return the bearer token to use for requests against *base_url*.

    Environment variable wins so CI, containers, and ad-hoc overrides
    never get shadowed by a stale file entry.
    """
    env_value = os.environ.get(ENV_VAR)
    if env_value and env_value.strip():
        return env_value.strip()
    data = _read_file()
    entry = data.get(host_for_url(base_url))
    if isinstance(entry, dict):
        token = entry.get("token")
        if isinstance(token, str) and token:
            return token
    return None


def save_token(host: str, token: str) -> None:
    data = _read_file()
    data[host] = {"token": token}
    _write_file(data)


def delete_token(host: str) -> bool:
    data = _read_file()
    if host in data:
        del data[host]
        _write_file(data)
        return True
    return False


def list_hosts() -> list[str]:
    return list(_read_file().keys())


def get_entry(host: str) -> dict | None:
    entry = _read_file().get(host)
    return entry if isinstance(entry, dict) else None
