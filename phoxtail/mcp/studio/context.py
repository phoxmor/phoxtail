"""MCP tool for assembling context briefings."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

from phoxtail.mcp import mcp_server
from phoxtail.mcp._http import request

_TEMPLATE_DIR = (
    Path(__file__).resolve().parent.parent.parent / "cli" / "templates" / "studio"
)
_jinja_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATE_DIR)),
    keep_trailing_newline=True,
)


@mcp_server.tool(
    name="phoxtail_studio_get_context",
    description=(
        "Get the full context document for working with a block variant. "
        "Returns a rendered briefing that includes the block's field schema, "
        "DTL syntax reference, CSS architecture rules, the variant's "
        "collection design tokens, the current variant's code, and "
        "optionally reference variants for inspiration. "
        "Call this before editing a variant to understand the domain "
        "constraints. To inspect a different collection's design system "
        "(e.g. for cross-collection creation), use "
        "phoxtail_studio_get_collection."
    ),
)
def get_context(
    block: str,
    variant: str,
    references: list[str] | None = None,
) -> str:
    body: dict[str, Any] = {"block": block, "variant": variant}
    if references:
        body["references"] = references
    resp = request("POST", "/context/", json_body=body)
    resp.raise_for_status()

    data = resp.json()
    template = _jinja_env.get_template("context.md")
    return template.render(**data)
