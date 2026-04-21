"""Phoxtail MCP server — the AI-agent interface to a Phoxtail project.

A single :class:`~mcp.server.fastmcp.FastMCP` instance is defined here.
Core domain sub-packages (``studio``, ``pages``) import it and register
their tools via ``@mcp_server.tool()``. Optional apps contribute
additional tools via the ``phoxtail.mcp_modules`` entry-point group —
each entry point is a dotted module path that is imported once at
startup, triggering its tool/resource/prompt registration.

Usage::

    phoxtail mcp serve
"""

from __future__ import annotations

import importlib
from importlib.metadata import entry_points

from mcp.server.fastmcp import FastMCP

mcp_server = FastMCP(
    "phoxtail",
    instructions=(
        "Phoxtail tools for managing a Phoxtail project. Tools are "
        "organized by domain: studio (block + variant editing), pages "
        "(Wagtail page read/write + publish + body editing). Optional "
        "apps contribute their own phoxtail_<app>_* tools (e.g. "
        "phoxtail_blog_list_authors when the blog app is installed). "
        "Always fetch a resource before updating it to get the current "
        "ETag for concurrency control. Use the design_block prompt and "
        "the phoxtail://schema-reference and phoxtail://page-types "
        "resources when creating new blocks or editing pages."
    ),
)


def _register_core_tools() -> None:
    """Import core domain modules to trigger tool/resource/prompt registration."""
    from phoxtail.mcp.pages import (  # noqa: F401
        body,
        media,
        pages,
    )
    from phoxtail.mcp.pages import (
        resources as pages_resources,
    )
    from phoxtail.mcp.studio import (  # noqa: F401
        blocks,
        collections,
        context,
        prompts,
        resources,
        variants,
    )


def _register_contributed_tools() -> None:
    """Import every module declared under the ``phoxtail.mcp_modules`` entry-point group.

    Called after ``_register_core_tools`` so that core tool names are
    registered first. Any installed package (bundled or third-party) can
    contribute MCP tools by declaring entry points in its pyproject.toml::

        [project.entry-points."phoxtail.mcp_modules"]
        my_app = "my_package.mcp"

    No Django runtime is required — discovery uses importlib.metadata.
    """
    for ep in entry_points(group="phoxtail.mcp_modules"):
        importlib.import_module(ep.value)


def _register_tools() -> None:
    _register_core_tools()
    _register_contributed_tools()


_register_tools()
