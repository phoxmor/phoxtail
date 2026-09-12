"""MCP tool for assembling context briefings."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

from phoxtail.mcp import mcp_server
from phoxtail.streams.mcp._http import request

_TEMPLATE_DIR = Path(__file__).resolve().parent.parent.parent / "cli" / "templates" / "studio"
_jinja_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATE_DIR)),
    keep_trailing_newline=True,
)


@mcp_server.tool(
    name="phoxtail_studio_get_context",
    description=(
        "Get the full context document for working with a block. Returns a "
        "rendered briefing that includes the block's field schema, DTL syntax "
        "reference, CSS architecture rules, site-wide design tokens (palettes, "
        "fonts), and optionally reference variants for inspiration. "
        "Pass `block_id` from phoxtail_studio_list_blocks. "
        "Optionally pass `collection_id` from phoxtail_studio_list_collections "
        "to include the collection label in the context. "
        "Call this before creating or editing a variant to understand "
        "the domain constraints."
    ),
)
def get_context(
    block_id: int,
    collection_id: int | None = None,
    references: list[int] | None = None,
) -> str:
    body: dict[str, Any] = {"block_id": block_id}
    if collection_id is not None:
        body["collection_id"] = collection_id
    if references:
        body["references"] = references
    resp = request("POST", "/context/", json_body=body)
    resp.raise_for_status()

    data = resp.json()
    template = _jinja_env.get_template("variant_design_context.md")
    return template.render(**data)
