"""Phoxtail MCP server — the AI-agent interface to a Phoxtail project.

A single :class:`~mcp.server.fastmcp.FastMCP` instance is defined here.
Domain sub-packages (``studio``, and future ``design``, ``pages``)
import it and register their tools via ``@mcp_server.tool()``.

Usage::

    phoxtail mcp serve
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

mcp_server = FastMCP(
    "phoxtail",
    instructions=(
        "Phoxtail tools for managing a Phoxtail project. "
        "Tools are organized by domain: studio (variant editing). "
        "Use phoxtail_studio_* tools for block variant operations. "
        "Always fetch a resource before updating it to get the "
        "current ETag for concurrency control."
    ),
)


def _register_tools() -> None:
    """Import domain modules to trigger tool registration."""
    from phoxtail.mcp.studio import blocks, collections, context, variants  # noqa: F401


_register_tools()
