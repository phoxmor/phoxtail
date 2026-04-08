"""CLI entry point for the Phoxtail MCP server.

Provides the ``phoxtail mcp serve`` command that starts the MCP stdio
server for AI-agent clients (Claude Code, Claude Desktop, etc.).
"""

from __future__ import annotations

import sys

import typer

app = typer.Typer(help="MCP server for AI agents.")


@app.command("serve")
def serve() -> None:
    """Start the MCP stdio server for AI agents.

    This command is intended to be launched by MCP clients (Claude Code,
    Claude Desktop) via their ``.mcp.json`` configuration, not by the
    user directly.
    """
    from phoxtail.mcp import mcp_server

    sys.stderr.write("Phoxtail MCP server starting (stdio)...\n")
    mcp_server.run(transport="stdio")
