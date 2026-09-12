"""Phoxtail MCP server — the AI-agent interface to a Phoxtail project.

A single :class:`~fastmcp.FastMCP` instance is defined here. Tools,
resources and prompts register themselves on it by import side-effect, via
``@mcp_server.tool()`` and friends.

Which modules get imported is not decided here. :func:`register_tools`
delegates to :mod:`phoxtail.core.discovery`, which walks every app that
subclasses ``PhoxtailAppConfig`` and imports what it finds in ``<pkg>/mcp/``.
Subclassing is the registration — there is no list in this module to append
to, and adding a file to an app's ``mcp/`` package is all it takes for its
tools to appear.

``register_tools`` needs a populated app registry, so the caller runs
``django.setup()`` first. ``phoxtail.cli.mcp.serve`` is that caller.

Usage::

    phoxtail mcp serve
"""

from __future__ import annotations

import importlib
import sys
from importlib.metadata import entry_points
from pathlib import Path

from fastmcp import FastMCP

# In dev mode the project root is bind-mounted read-write at /app, so mkdir
# here propagates to the host. Guard with is_dir() so this is a no-op on the
# host (local imports, tests) where /app doesn't exist.
_container_root = Path("/app")
if _container_root.is_dir():
    (_container_root / ".phoxtail" / "mcp" / "uploads").mkdir(parents=True, exist_ok=True)

# Imported before the server is built: `auth` cannot be attached
# afterwards, because it is what decides whether the HTTP route is wrapped
# in a challenge at all.
from phoxtail.mcp.authorization import WhoamiVerifier  # noqa: E402

mcp_server = FastMCP(
    "phoxtail",
    # Only the HTTP transport consults this. Over stdio there is no inbound
    # credential and nothing to resolve — the process already runs as
    # whoever started it, and fastmcp skips authorization there entirely.
    auth=WhoamiVerifier(),
    # Two tools may not share a name. fastmcp's own default for a component
    # store is "error"; FastMCP softens that to "warn", which registers the
    # second one over the first and logs a line nobody reads. That is the wrong
    # trade now that a tool exists because a file exists: a copy-pasted module,
    # or two apps reaching for the same name, would silently replace a core
    # tool with no way to notice. Refusing at startup is how the collision
    # reaches a person.
    on_duplicate="error",
    instructions=(
        "Phoxtail tools for managing a Phoxtail project. Tools are "
        "organized by domain: studio (block + variant editing), content "
        "(Wagtail page read/write + body editing, sites, locales), users "
        "(user + gender management, bulk user import, email verification — "
        "every "
        "phoxtail_users_* tool requires a superuser token/session), agent "
        "(the chatbot's inference providers, selectable models and per-site "
        "default model), dashboard (the menus shown on the platform's own "
        "screens). Optional "
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


def _register_unmigrated_tools() -> None:
    """Import the tool modules that do not yet live inside their own app.

    TRANSITIONAL. Two reasons a module is listed here rather than discovered:

    * the code sits under ``phoxtail/mcp/`` instead of in the app package —
      cms owns ``content`` and ``cms``;
    * or the app is not a ``PhoxtailAppConfig`` yet, so discovery cannot see
      it at all. That is why ``phoxtail.users.mcp`` is here despite already
      living inside its app.

    As each app is migrated, its lines are deleted from here — in the same
    commit as the move. A module that is both listed here and discovered in
    its app is registered twice, and two tools may not share a name, so the
    server refuses to start. That is the behaviour we want and it reads as
    "phoxtail will not boot", so: move and delete together.

    This function goes away when the list empties.
    """
    import phoxtail.mcp.cms.site_setting_fonts  # noqa: F401
    import phoxtail.mcp.cms.site_setting_palettes  # noqa: F401
    import phoxtail.mcp.cms.site_settings  # noqa: F401
    import phoxtail.mcp.content.blocks  # noqa: F401
    import phoxtail.mcp.content.body  # noqa: F401
    import phoxtail.mcp.content.collections  # noqa: F401
    import phoxtail.mcp.content.pages  # noqa: F401
    import phoxtail.mcp.content.resources  # noqa: F401
    import phoxtail.mcp.content.sites  # noqa: F401
    import phoxtail.mcp.peers  # noqa: F401
    import phoxtail.users.mcp.genders  # noqa: F401
    import phoxtail.users.mcp.users  # noqa: F401


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

    from phoxtail.cli.utils.config import find_config_file, get_mcp_extra_modules

    extra = get_mcp_extra_modules()
    if extra:
        config_file = find_config_file()
        if config_file is not None:
            project_root = str(config_file.parent)
            if project_root not in sys.path:
                sys.path.insert(0, project_root)

    for dotted in extra:
        importlib.import_module(dotted)


_registered = False


def register_tools() -> None:
    """Register every tool, resource and prompt this project exposes.

    Call after ``django.setup()`` — discovery reads the app registry.
    Registration happens as a side effect of importing a module, so the loop
    has nothing to do. Idempotent: the MCP server calls it at startup, and the
    chatbot calls it the first time it needs the catalogue, and neither has to
    know about the other.

    Discovery is the rule; the two other calls are transitional scaffolding for
    surfaces that have not moved into their app yet.
    """
    global _registered
    if _registered:
        return

    from phoxtail.core.discovery import discover_submodules

    _register_unmigrated_tools()
    for _name, _module in discover_submodules("mcp"):
        pass
    _register_contributed_tools()

    _registered = True
