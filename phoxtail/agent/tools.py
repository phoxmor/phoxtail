"""PydanticAI Tool wrappers around FastMCP tools."""

from __future__ import annotations

from typing import Any

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

    async def prepare(
        ctx: RunContext[None], tool_def: ToolDefinition
    ) -> ToolDefinition:
        return ToolDefinition(
            name=mcp_tool.name,
            description=mcp_tool.description or "",
            parameters_json_schema=mcp_tool.parameters,
        )

    return Tool(
        fn, name=mcp_tool.name, description=mcp_tool.description or "", prepare=prepare
    )


def get_tools() -> list[Tool]:
    return [_make_tool(t) for t in _get_mcp_tools().values()]
