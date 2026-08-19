"""PydanticAI Tool wrappers around FastMCP tools."""

from __future__ import annotations

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


def _get_mcp_tools() -> dict:
    from phoxtail.mcp import mcp_server

    return mcp_server._tool_manager._tools


def _make_tool(mcp_tool) -> Tool:
    """Wrap a single FastMCP tool as a PydanticAI Tool."""

    async def fn(ctx: RunContext[None], **kwargs: Any) -> str:
        import json

        try:
            result = await mcp_tool.run(kwargs, context=None, convert_result=False)
            return result if isinstance(result, str) else json.dumps(result)
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
    return [_make_tool(t) for t in _get_mcp_tools().values()]
