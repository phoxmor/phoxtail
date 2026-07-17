"""Shared error envelope helper for users MCP tools."""

from __future__ import annotations

import json


def error_envelope(resp) -> str | None:
    """Return a JSON error string for non-2xx responses, or None on success."""
    sc = resp.status_code
    if 200 <= sc < 300:
        return None

    hints = {
        401: ("Authentication failed. The users tools require a valid token or session."),
        403: ("Permission denied. The users tools require an active superuser token/session."),
        412: ("The resource has been modified since you last read it. Re-fetch to get the current ETag, then retry."),
        428: ("ETag is required. Fetch the resource first and pass the `_etag` value from the response."),
        422: "Validation failed — check the field values against the tool description.",
        404: "Resource not found.",
    }

    try:
        detail = resp.json().get("detail", hints.get(sc, resp.text))
    except Exception:
        detail = hints.get(sc, resp.text)

    return json.dumps({"error": True, "status": sc, "detail": detail})
