"""Shared error envelope helper for dashboard MCP tools."""

from __future__ import annotations

import json


def error_envelope(resp) -> str | None:
    """Return a JSON error string for non-2xx responses, or None on success."""
    status = resp.status_code
    if 200 <= status < 300:
        return None

    hints = {
        401: "Authentication failed. The dashboard tools require a valid token or session.",
        404: "Menu not found.",
        403: "Permission denied.",
        409: "A menu for that site and language already exists — update it instead of creating a second one.",
        412: "The menu has changed since you last read it. Re-fetch to get the current ETag, then retry.",
        428: "ETag is required. Fetch the menu first and pass the `_etag` value from the response.",
        422: "Validation failed — check the entries against the tool description.",
    }

    try:
        detail = resp.json().get("detail", hints.get(status, resp.text))
    except Exception:
        detail = hints.get(status, resp.text)

    return json.dumps({"error": True, "status": status, "detail": detail})
