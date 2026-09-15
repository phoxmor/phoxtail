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


async def tools_for_caller() -> list:
    """The tools the current caller may be offered, asked fresh.

    **Deliberately not cached, where this used to be.** The list was read
    once per process and reused for everybody, which was right while every
    caller was the same caller. Once a turn carries its own credential the
    catalogue is a fact about the person, and a process-wide cache would
    hand the first person's answer to the second.

    The narrowing is not done here and there is nothing here that knows
    about permissions. ``list_tools`` asks each tool its own question and
    the answers depend on the credential in context, which the caller has
    already set. This only asks.
    """
    from phoxtail.mcp import mcp_server, register_tools

    # The tool surface is discovered from the app registry rather than
    # registered when phoxtail.mcp is imported, so ask for it. Idempotent,
    # and the registry is long since populated here.
    register_tools()
    return list(await mcp_server.list_tools())


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


async def toolset_for_caller():
    """The current caller's tools, as something one agent run can be given.

    Returned as a toolset rather than baked into the agent, because the
    agent is memoised per model and shared by everyone using it, while
    this list belongs to one person. pydantic-ai adds a run's toolsets to
    whatever the agent already carries, so the agent must carry none of
    these — anything baked in would reach every caller regardless of what
    they may do.
    """
    _import_pydantic_ai()
    from pydantic_ai.toolsets import FunctionToolset

    return FunctionToolset(tools=[_make_tool(t) for t in await tools_for_caller()])
