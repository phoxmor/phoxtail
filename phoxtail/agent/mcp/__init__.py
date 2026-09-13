"""Agent MCP tools — the provider catalogue as an agent-writable surface.

Importing ``phoxtail.mcp`` here, before any submodule runs, is what keeps
a direct ``import phoxtail.agent.mcp.providers`` working: that package's
``__init__`` registers every core tool module, this one included, so a
submodule reached first would otherwise re-enter its own ``_http`` while
that module is still executing.
"""

from __future__ import annotations

import phoxtail.mcp  # noqa: F401
