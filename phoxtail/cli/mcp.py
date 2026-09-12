"""CLI entry point for the Phoxtail MCP server.

Provides the ``phoxtail mcp serve`` command that starts the MCP stdio
server for AI-agent clients (Claude Code, Claude Desktop, etc.).
"""

from __future__ import annotations

import os
import sys

import typer

app = typer.Typer(help="MCP server for AI agents.")


def _setup_django() -> None:
    """Boot Django the way the project's own ``manage.py`` does.

    The tool surface is discovered from the app registry, so the registry has
    to exist before any tool module is imported.

    Deliberately the same two moves ``manage.py`` and ``wsgi.py`` make, rather
    than new configuration: the project root goes on ``sys.path`` so ``src``
    is importable, and ``DJANGO_ENV`` names the settings module. A console
    script's ``sys.path[0]`` is the directory the script lives in, not the
    working directory, which is the whole reason the first move is needed and
    ``manage.py`` — run as a file from the project root — never was.

    ``setdefault`` throughout, so an operator who has already set either one
    keeps their answer.
    """
    import django
    from django.core.exceptions import ImproperlyConfigured

    from phoxtail.cli.utils.config import find_config_file

    config_file = find_config_file()
    if config_file is not None:
        project_root = str(config_file.parent)
        if project_root not in sys.path:
            sys.path.insert(0, project_root)

    django_env = os.environ.get("DJANGO_ENV", "development")
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", f"src.settings.{django_env}")

    try:
        django.setup()
    except (ImproperlyConfigured, ModuleNotFoundError) as exc:
        # Only the two failures that mean "the project is not here". Django's
        # own message names an environment variable without saying which
        # process could not find the project, and that is the actual problem.
        #
        # Deliberately narrow: an app raising during setup is a broken app, and
        # telling its author to cd somewhere else would send them looking in
        # the wrong place. That one keeps its own traceback.
        raise typer.BadParameter(
            f"The MCP server needs the project's Django settings and cannot load "
            f"them from here: {exc} Run it from the project directory, or from "
            f"its container with `docker compose exec web phoxtail mcp serve`."
        ) from exc


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
    # Django first: the tool surface is discovered from the app registry
    # (see phoxtail.core.discovery), so the registry has to exist before any
    # tool module is imported. Done here, at the process entry point, rather
    # than as an import side-effect of phoxtail.mcp — that module is also
    # imported by tests and by the web process, which set themselves up.
    _setup_django()

    from phoxtail.mcp import mcp_server, register_tools

    register_tools()

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
