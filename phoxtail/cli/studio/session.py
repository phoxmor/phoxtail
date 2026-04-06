"""Host-side session management for Phoxtail Studio editing sessions.

Sessions are working copies stored at ``.phoxtail/studio/<session-id>/``
relative to the project root (the directory containing ``phoxtail.toml``).

This module handles all filesystem operations for sessions. It never
imports Django, httpx, or any API concern — it only reads and writes
files the CLI has on disk. The API knows nothing about sessions: they
are a purely client-side convention.
"""

from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

from phoxtail.cli.utils.config import _find_config_file

STUDIO_DIR = ".phoxtail/studio"

# File names inside a session directory
SESSION_META = "session.json"
SESSION_HTML = "template.html"
SESSION_CSS = "style.css"
SESSION_JS = "script.js"
SESSION_CONTEXT = "context.md"


def _project_root() -> Path:
    config = _find_config_file()
    if config is None:
        raise FileNotFoundError("No phoxtail.toml found")
    return config.parent


def sessions_root() -> Path:
    return _project_root() / STUDIO_DIR


def session_dir(session_id: str) -> Path:
    return sessions_root() / session_id


def session_exists(session_id: str) -> bool:
    return (session_dir(session_id) / SESSION_META).is_file()


def create_session(
    session_id: str,
    variant_data: dict,
    context_md: str,
    template_used: str,
    etag: str,
) -> Path:
    """Write session files to disk. Returns the session directory path.

    ``etag`` is the value returned by ``GET /variants/{id}`` and is
    stored in ``session.json`` so that ``commit`` can send it back as
    ``If-Match`` for optimistic concurrency control.
    """
    sdir = session_dir(session_id)
    sdir.mkdir(parents=True, exist_ok=True)

    # Write the three editable files
    (sdir / SESSION_HTML).write_text(variant_data.get("html", ""))
    (sdir / SESSION_CSS).write_text(variant_data.get("css", ""))
    (sdir / SESSION_JS).write_text(variant_data.get("javascript", ""))

    # Write context.md (the rendered system prompt)
    (sdir / SESSION_CONTEXT).write_text(context_md)

    # Write session metadata
    meta = {
        "session_id": session_id,
        "variant": {
            "identifier": variant_data["identifier"],
            "name": variant_data["name"],
            "block": variant_data["block"],
            "collection": variant_data["collection"],
        },
        "started_at": datetime.now(UTC).isoformat(),
        "template": template_used,
        "etag": etag,
        "message": None,
    }
    (sdir / SESSION_META).write_text(json.dumps(meta, indent=2))

    return sdir


def read_session(session_id: str) -> dict:
    """Read session metadata and file contents. Returns a dict."""
    sdir = session_dir(session_id)
    meta_path = sdir / SESSION_META
    if not meta_path.is_file():
        raise FileNotFoundError(f"Session '{session_id}' not found.")

    meta = json.loads(meta_path.read_text())
    meta["html"] = (sdir / SESSION_HTML).read_text()
    meta["css"] = (sdir / SESSION_CSS).read_text()
    meta["javascript"] = (sdir / SESSION_JS).read_text()
    return meta


def list_sessions() -> list[dict]:
    """Return metadata for all active sessions."""
    root = sessions_root()
    if not root.is_dir():
        return []

    sessions = []
    for child in sorted(root.iterdir()):
        meta_path = child / SESSION_META
        if child.is_dir() and meta_path.is_file():
            try:
                meta = json.loads(meta_path.read_text())
                meta["path"] = str(child)
                sessions.append(meta)
            except (json.JSONDecodeError, OSError):
                continue
    return sessions


def discard_session(session_id: str) -> Path:
    """Delete a session directory. Returns the path that was removed."""
    sdir = session_dir(session_id)
    if not sdir.is_dir():
        raise FileNotFoundError(f"Session '{session_id}' not found.")
    shutil.rmtree(sdir)
    return sdir


def derive_session_id(variant_identifier: str) -> str:
    """Derive a session ID from a variant identifier.

    Uses the variant identifier directly. If a session already exists
    for that identifier, appends a short numeric suffix.
    """
    base = variant_identifier
    if not session_exists(base):
        return base

    n = 2
    while session_exists(f"{base}-{n}"):
        n += 1
    return f"{base}-{n}"
