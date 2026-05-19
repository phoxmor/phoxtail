"""Phoxtail MCP server — the AI-agent interface to a Phoxtail project.

A single :class:`~mcp.server.fastmcp.FastMCP` instance is defined here.
Core domain sub-packages (``studio``, ``content``) import it and register
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
        "organized by domain: studio (block + variant editing), content "
        "(Wagtail page read/write + body editing, sites, locales). Optional "
        "apps contribute their own phoxtail_<app>_* tools (e.g. "
        "phoxtail_blog_list_authors when the blog app is installed). "
        "Always fetch a resource before updating it to get the current "
        "ETag for concurrency control. Use the design_block prompt and "
        "the phoxtail://schema-reference and phoxtail://page-types "
        "resources when creating new blocks or editing pages. "
        "IMPORTANT: never call phoxtail_pages_publish unless the user "
        "explicitly asks to publish. Every write operation (create, update, "
        "add/update/delete/move blocks, replace body) saves a draft revision "
        "only — the page stays unpublished so the user can review changes "
        "before deciding to go live."
    ),
)


def _register_core_tools() -> None:
    """Import core domain modules to trigger tool/resource/prompt registration."""
    import phoxtail.mcp.cms.site_setting_fonts  # noqa: F401
    import phoxtail.mcp.cms.site_setting_palettes  # noqa: F401
    import phoxtail.mcp.cms.site_settings  # noqa: F401
    import phoxtail.mcp.content.blocks  # noqa: F401
    import phoxtail.mcp.content.body  # noqa: F401
    import phoxtail.mcp.content.collections  # noqa: F401
    import phoxtail.mcp.content.internal_links  # noqa: F401
    import phoxtail.mcp.content.media  # noqa: F401
    import phoxtail.mcp.content.pages  # noqa: F401
    import phoxtail.mcp.content.resources  # noqa: F401
    import phoxtail.mcp.content.sites  # noqa: F401
    import phoxtail.mcp.design.font_families  # noqa: F401
    import phoxtail.mcp.design.font_roles  # noqa: F401
    import phoxtail.mcp.design.font_weights  # noqa: F401
    import phoxtail.mcp.design.palette_roles  # noqa: F401
    import phoxtail.mcp.design.palette_sets  # noqa: F401
    import phoxtail.mcp.design.palettes  # noqa: F401
    import phoxtail.mcp.studio.blocks  # noqa: F401
    import phoxtail.mcp.studio.collections  # noqa: F401
    import phoxtail.mcp.studio.context  # noqa: F401
    import phoxtail.mcp.studio.prompts  # noqa: F401
    import phoxtail.mcp.studio.render  # noqa: F401
    import phoxtail.mcp.studio.resources  # noqa: F401
    import phoxtail.mcp.studio.sessions  # noqa: F401
    import phoxtail.mcp.studio.shared_blocks  # noqa: F401
    import phoxtail.mcp.studio.variants  # noqa: F401


def _register_contributed_tools() -> None:
    """Import every module in the ``phoxtail.mcp_modules`` entry-point group,
    then any project-local modules declared under ``[mcp] extra_modules`` in
    ``phoxtail.toml``.

    Called after ``_register_core_tools`` so that core tool names are
    registered first. Library apps contribute via pyproject.toml entry points::

        [project.entry-points."phoxtail.mcp_modules"]
        my_app = "my_package.mcp"

    Project-local apps (plain directories, no pyproject.toml) use
    ``phoxtail.toml`` instead::

        [mcp]
        extra_modules = ["my_project_app.mcp"]

    No Django runtime is required — both discovery paths read only from
    importlib.metadata and TOML files.
    """
    for ep in entry_points(group="phoxtail.mcp_modules"):
        importlib.import_module(ep.value)

    from phoxtail.cli.utils.config import get_mcp_extra_modules

    for dotted in get_mcp_extra_modules():
        importlib.import_module(dotted)


def _register_tools() -> None:
    _register_core_tools()
    _register_contributed_tools()


_register_tools()
