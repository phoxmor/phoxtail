"""PydanticAI Tool wrappers around FastMCP tools."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pydantic_ai import RunContext, Tool, ToolDefinition


def _import_pydantic_ai() -> None:
    """Bind pydantic_ai names into module globals on first use.

    Deferred because this module loads at django.setup() via the chat router,
    and pydantic_ai costs ~50MB RSS per process. The names must land in
    globals (not function locals) because Tool() resolves the tool functions'
    string annotations (e.g. ``RunContext[None]``) against this module's
    namespace via get_type_hints().
    """
    global RunContext, Tool, ToolDefinition
    from pydantic_ai import RunContext, Tool, ToolDefinition


_mcp_tools: list | None = None
_prime_lock: asyncio.Lock | None = None


async def prime_tools() -> None:
    """Fetch the registered FastMCP tools into a module-level cache.

    Reading the registry is async — ``list_tools`` applies the server's
    transforms and filtering — but the agent factory below it is a
    synchronous, memoised function that cannot await. Registration happens
    once at import time and never changes afterwards, so priming the cache
    once per process is both correct and cheap; callers await this before
    building an agent.
    """
    global _mcp_tools, _prime_lock
    if _mcp_tools is not None:
        return
    # Built lazily: the lock must belong to the running loop, and there is
    # none at import time.
    if _prime_lock is None:
        _prime_lock = asyncio.Lock()
    async with _prime_lock:
        if _mcp_tools is None:
            from phoxtail.mcp import mcp_server

            _mcp_tools = list(await mcp_server.list_tools())


def _make_tool(mcp_tool) -> Tool:
    """Wrap a single FastMCP tool as a PydanticAI Tool."""

    async def fn(ctx: RunContext[None], **kwargs: Any) -> str:
        import json

        try:
            result = await mcp_tool.run(kwargs)
            text = "\n".join(b.text for b in result.content if getattr(b, "text", None))
            return text or json.dumps(result.structured_content or {})
        except Exception as exc:
            return json.dumps({"error": str(exc)})

    fn.__name__ = mcp_tool.name

    async def prepare(ctx: RunContext[object], tool_def: ToolDefinition) -> ToolDefinition:
        return ToolDefinition(
            name=mcp_tool.name,
            description=mcp_tool.description or "",
            parameters_json_schema=mcp_tool.parameters,
        )

    return Tool(fn, name=mcp_tool.name, description=mcp_tool.description or "", prepare=prepare)


def get_tools() -> list[Tool]:
    _import_pydantic_ai()
    if _mcp_tools is None:
        raise RuntimeError("prime_tools() must be awaited before get_tools().")
    return [_make_tool(t) for t in _mcp_tools]
