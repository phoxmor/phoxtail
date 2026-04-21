"""MCP prompts for the studio domain."""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from phoxtail.mcp import mcp_server
from phoxtail.mcp.studio._http import get_json

_TEMPLATE_DIR = (
    Path(__file__).resolve().parent.parent.parent / "cli" / "templates" / "studio"
)
_jinja_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATE_DIR)),
    keep_trailing_newline=True,
)


@mcp_server.prompt(
    name="design_block",
    description=(
        "Guide an agent through designing a new block schema. "
        "Provide a description of the block's purpose and optionally "
        "a reference URL for design inspiration."
    ),
)
def design_block(
    description: str,
    reference_url: str | None = None,
) -> str:
    template = _jinja_env.get_template("block_design_context.md")
    return template.render(
        description=description,
        reference_url=reference_url,
        schema_catalog=get_json("/schema-catalog/"),
    )
