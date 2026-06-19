"""MCP tools for session-based variant editing.

Sessions are filesystem working copies stored at
``~/.phoxtail/projects/<project-key>/sessions/<session-id>/``.
An agent opens a session to get local file paths, uses its native
Read/Edit tools for surgical changes, then commits the session to
push the result back to the database.  This is faster and more
token-efficient than the direct get/update route because Edit only
sends the changed lines rather than the full content of every field.
"""

from __future__ import annotations

import json
from pathlib import Path

from phoxtail.cli.studio import session as _session
from phoxtail.mcp import mcp_server
from phoxtail.mcp.studio._http import request

_NEXT_STEPS = (
    "Use your filesystem Read and Edit tools on the paths in `files` to make "
    "changes. Do NOT call phoxtail_studio_get_variant to reload content — "
    "the files on disk are the working copy. When finished, call "
    "phoxtail_studio_commit_variant to write the changes back to the database. "
    "Note: only `html`, `css`, and `javascript` are committed; `context` is "
    "reference material only — edits to it are not saved to the database."
)

_TEMPLATE_DIR = Path(__file__).resolve().parent.parent.parent / "cli" / "templates" / "studio"


def _file_paths(sdir: Path) -> dict:
    return {
        "html": str(sdir / _session.SESSION_HTML),
        "css": str(sdir / _session.SESSION_CSS),
        "javascript": str(sdir / _session.SESSION_JS),
        "context": str(sdir / _session.SESSION_CONTEXT),
    }


def _resolve(session_id: str | None) -> str | dict:
    """Return a resolved session_id string, or an error dict."""
    if session_id is not None:
        sdir = _session.session_dir(session_id)
        try:
            if not sdir.resolve().is_relative_to(_session.sessions_root().resolve()):
                return {
                    "error": "invalid_session_id",
                    "detail": "session_id must not contain path traversal components.",
                }
        except (ValueError, OSError):
            return {
                "error": "invalid_session_id",
                "detail": "session_id must not contain path traversal components.",
            }
        if not _session.session_exists(session_id):
            return {
                "error": "not_found",
                "detail": f"Session '{session_id}' not found.",
            }
        return session_id
    active = _session.list_sessions()
    if not active:
        return {"error": "no_sessions", "detail": "No active sessions."}
    if len(active) > 1:
        ids = [s["session_id"] for s in active]
        return {
            "error": "ambiguous",
            "detail": (f"Multiple active sessions: {ids}. Pass `session_id` to disambiguate."),
            "sessions": ids,
        }
    return active[0]["session_id"]


# -- Open ------------------------------------------------------------------


@mcp_server.tool(
    name="phoxtail_studio_open_variant",
    description=(
        "Open a variant for session-based editing. Fetches the variant from the "
        "database, writes its HTML, CSS, and JavaScript to local files, and "
        "returns the absolute paths of those files plus a context briefing. "
        "IMPORTANT: after calling this, use your filesystem Read and Edit tools "
        "on the returned `files` paths to make changes — do NOT call "
        "phoxtail_studio_get_variant to reload content. Edit shows a surgical "
        "diff per change which is more token-efficient and gives you a preview "
        "before each write. When all edits are done, call "
        "phoxtail_studio_commit_variant to push the session back to the database. "
        "Idempotent: if a session for this variant is already open, the existing "
        "session path is returned without overwriting local edits."
    ),
)
def open_variant(variant_id: int) -> str:
    resp = request("GET", f"/variants/{variant_id}/")
    resp.raise_for_status()
    variant_data = resp.json()
    etag = resp.headers.get("ETag", "")

    session_id = str(variant_data["id"])

    if _session.session_exists(session_id):
        sdir = _session.session_dir(session_id)
        existing_meta = _session.read_session(session_id)
        return json.dumps(
            {
                "session_id": session_id,
                "path": str(sdir),
                "status": "already_open",
                "files": _file_paths(sdir),
                "variant": existing_meta["variant"],
                "next_steps": _NEXT_STEPS,
            },
            indent=2,
        )

    context_md = _render_context(variant_data)

    sdir = _session.create_session(
        session_id=session_id,
        variant_data=variant_data,
        context_md=context_md,
        template_used="context",
        etag=etag,
    )

    return json.dumps(
        {
            "session_id": session_id,
            "path": str(sdir),
            "status": "opened",
            "files": _file_paths(sdir),
            "variant": {
                "id": variant_data["id"],
                "identifier": variant_data["identifier"],
                "name": variant_data["name"],
                "block": variant_data["block"],
                "collection": variant_data["collection"],
            },
            "next_steps": _NEXT_STEPS,
        },
        indent=2,
    )


def _render_context(variant_data: dict) -> str:
    try:
        from jinja2 import Environment, FileSystemLoader

        jinja_env = Environment(
            loader=FileSystemLoader(str(_TEMPLATE_DIR)),
            keep_trailing_newline=True,
        )
        _collection = variant_data.get("collection") or {}
        ctx_body: dict = {"block_id": variant_data["block"]["id"]}
        if _collection.get("id") is not None:
            ctx_body["collection_id"] = _collection["id"]
        ctx_resp = request("POST", "/context/", json_body=ctx_body)
        if ctx_resp.is_success:
            return jinja_env.get_template("variant_design_context.md").render(**ctx_resp.json())
    except Exception:
        pass
    return ""


# -- Commit ----------------------------------------------------------------


@mcp_server.tool(
    name="phoxtail_studio_commit_variant",
    description=(
        "Write an open session's local files back to the database. "
        "Reads template.html, style.css, and script.js from the session "
        "directory and PUTs them to the API using the stored ETag for "
        "optimistic concurrency control. "
        "Pass `session_id` when more than one session is active; it can be "
        "omitted when only one session exists. "
        "Set `clean=true` to delete the session directory after a successful "
        "commit (default: false — the session is kept so you can inspect the "
        "result or make follow-up edits). "
        "On a 412 conflict the session is always preserved; call "
        "phoxtail_studio_refresh_session to re-sync the ETag, then retry."
    ),
)
def commit_variant(
    session_id: str | None = None,
    clean: bool = False,
) -> str:
    resolved = _resolve(session_id)
    if isinstance(resolved, dict):
        return json.dumps(resolved)
    session_id = resolved

    data = _session.read_session(session_id)
    variant_meta = data["variant"]
    etag = data.get("etag") or ""

    if not etag:
        return json.dumps(
            {
                "error": "no_etag",
                "detail": (
                    "Session has no stored ETag — it was created before optimistic "
                    "concurrency was wired. Discard it and open a new session."
                ),
            }
        )

    resp = request(
        "PUT",
        f"/variants/{variant_meta['id']}/",
        json_body={
            "html": data["html"],
            "css": data["css"],
            "javascript": data["javascript"],
        },
        headers={"If-Match": etag},
    )

    if resp.status_code == 412:
        return json.dumps(
            {
                "error": "conflict",
                "detail": (
                    "The variant was modified on the server since this session was "
                    "opened. Call phoxtail_studio_refresh_session to update the stored "
                    "ETag, then call phoxtail_studio_commit_variant again."
                ),
            }
        )
    if resp.status_code == 428:
        return json.dumps(
            {
                "error": "precondition_required",
                "detail": (
                    "ETag is required but missing. Discard this session and open a "
                    "new one with phoxtail_studio_open_variant."
                ),
            }
        )

    resp.raise_for_status()
    updated = resp.json()
    new_etag = resp.headers.get("ETag", "")

    if clean:
        _session.discard_session(session_id)
    elif new_etag:
        _session.update_session_etag(session_id, new_etag)

    return json.dumps(
        {
            "status": "committed",
            "session_id": session_id,
            "session_cleaned": clean,
            "variant": {
                "id": updated["id"],
                "identifier": updated["identifier"],
                "name": updated["name"],
                "block": updated.get("block", {}),
                "collection": updated.get("collection"),
            },
            "_etag": new_etag,
        },
        indent=2,
    )


# -- Discard ---------------------------------------------------------------


@mcp_server.tool(
    name="phoxtail_studio_discard_variant",
    description=(
        "Discard an open session without saving any changes. "
        "Deletes the session directory from the filesystem permanently. "
        "Pass `session_id` when more than one session is active; it can be "
        "omitted when only one session exists."
    ),
)
def discard_variant(session_id: str | None = None) -> str:
    resolved = _resolve(session_id)
    if isinstance(resolved, dict):
        return json.dumps(resolved)
    session_id = resolved

    _session.discard_session(session_id)
    return json.dumps({"status": "discarded", "session_id": session_id})


# -- List ------------------------------------------------------------------


@mcp_server.tool(
    name="phoxtail_studio_list_sessions",
    description=(
        "List all open editing sessions for the current project. "
        "Returns session ID, variant, block, collection, and started timestamp "
        "for each active session. Use this to discover sessions left open from "
        "previous conversations before starting new work."
    ),
)
def list_sessions() -> str:
    sessions = _session.list_sessions()
    return json.dumps({"sessions": sessions, "total": len(sessions)}, indent=2)


# -- Refresh ---------------------------------------------------------------


@mcp_server.tool(
    name="phoxtail_studio_refresh_session",
    description=(
        "Re-fetch the current ETag for a session's variant from the server "
        "without touching the local working files. "
        "Call this after a phoxtail_studio_commit_variant returns a 'conflict' "
        "error (412) to synchronise the stored ETag, then inspect the local "
        "files for conflicts before retrying the commit. "
        "Pass `session_id` when more than one session is active."
    ),
)
def refresh_session(session_id: str | None = None) -> str:
    resolved = _resolve(session_id)
    if isinstance(resolved, dict):
        return json.dumps(resolved)
    session_id = resolved

    data = _session.read_session(session_id)
    variant_meta = data["variant"]

    resp = request("GET", f"/variants/{variant_meta['id']}/")
    resp.raise_for_status()
    new_etag = resp.headers.get("ETag", "")

    if not new_etag:
        return json.dumps(
            {
                "error": "no_etag",
                "detail": "Server returned no ETag for this variant.",
            }
        )

    _session.update_session_etag(session_id, new_etag)
    return json.dumps(
        {
            "status": "refreshed",
            "session_id": session_id,
            "_etag": new_etag,
        }
    )
