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
        "Get the full context document for working with a block in a "
        "given collection. Returns a rendered briefing that includes "
        "the block's field schema, DTL syntax reference, CSS "
        "architecture rules, the collection's design guidelines, "
        "site-wide design tokens (palettes, fonts), and optionally "
        "reference variants for inspiration. "
        "Call this before creating or editing a variant to understand "
        "the domain constraints."
    ),
)
def get_context(
    block: str,
    collection: str,
    references: list[str] | None = None,
) -> str:
    body: dict[str, Any] = {"block": block, "collection": collection}
    if references:
        body["references"] = references
    resp = request("POST", "/context/", json_body=body)
    resp.raise_for_status()

    data = resp.json()
    template = _jinja_env.get_template("variant_design_context.md")
    return template.render(**data)
