"""CLI entry point for the Phoxtail MCP server.

Provides the ``phoxtail mcp serve`` command that starts the MCP stdio
server for AI-agent clients (Claude Code, Claude Desktop, etc.).
"""

from __future__ import annotations

import sys

import typer

app = typer.Typer(help="MCP server for AI agents.")


@app.command("serve")
def serve(
    http: bool = typer.Option(
        False,
        "--http",
        help=(
            "Serve over streamable HTTP instead of stdio — an always-on server "
            "any MCP client (or sibling project) can connect to at /mcp."
        ),
    ),
    host: str = typer.Option("127.0.0.1", "--host", help="Bind address for --http."),
    port: int = typer.Option(8001, "--port", help="Bind port for --http."),
) -> None:
    """Start the MCP server for AI agents.

    Without flags: the stdio transport, intended to be launched by MCP
    clients (Claude Code, Claude Desktop) via their ``.mcp.json``
    configuration, not by the user directly.

    With ``--http``: the streamable-http transport. The server holds no
    credentials of its own for callers — each request's Bearer token is
    forwarded to the project API, which validates it, so callers
    authenticate with the same tokens ``phoxtail auth login`` stores.
    """
    from phoxtail.mcp import mcp_server

    if not http:
        sys.stderr.write("Phoxtail MCP server starting (stdio)...\n")
        mcp_server.run(transport="stdio")
        return

    import uvicorn

    from phoxtail.cli.utils.config import find_config_file, get_project_name, slugify

    # DNS-rebinding protection rejects any Host header not allowlisted
    # (421). Loopback covers direct local runs; the project's own MCP
    # hostname covers both real paths — Traefik forwards it from the host,
    # siblings send it via the network alias. No Origin is allowed at all:
    # MCP clients don't send one, browsers must not call this directly.
    allowed_hosts = ["localhost", "localhost:*", "127.0.0.1", "127.0.0.1:*"]
    if find_config_file() is not None:
        slug = slugify(get_project_name())
        allowed_hosts += [f"mcp.{slug}.localhost", f"mcp.{slug}.localhost:*"]

    # host_origin_protection is passed explicitly because it defaults to
    # False: an app built with allowed_hosts alone installs no guard at
    # all and answers every Host with 200, silently.
    app = mcp_server.http_app(
        path="/mcp",
        allowed_hosts=allowed_hosts,
        allowed_origins=[],
        host_origin_protection=True,
    )

    sys.stderr.write(f"Phoxtail MCP server starting (streamable-http on {host}:{port}, path /mcp)...\n")
    uvicorn.run(app, host=host, port=port, log_level="warning")
