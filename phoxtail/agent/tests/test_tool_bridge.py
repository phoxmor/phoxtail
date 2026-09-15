"""The chatbot's tools belong to the caller, not to the process.

The bug this replaces was one cache. The tool list was read once and
reused for everybody, which was right while every caller was the same
caller — the operator whose credential the container holds. Once a turn
carries its own credential, the catalogue is a fact about the person, and
a shared list hands the first person's answer to the second.

Two properties keep that from coming back, and each would be undone by a
plausible tidy-up:

- the list is asked for again per caller, not remembered;
- the MCP tools reach a run rather than the agent, because the agent is
  memoised per model and shared by everyone using it.

The second is the one with teeth. Anything built into the agent is
offered to every caller whatever their credential says, which is the
failure this whole change exists to prevent — and it would look like a
harmless simplification in review.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest


class TestTheListIsPerCaller:
    def test_it_asks_again_rather_than_remembering(self, monkeypatch):
        calls = []

        async def list_tools():
            calls.append(1)
            return []

        monkeypatch.setattr("phoxtail.mcp.mcp_server", SimpleNamespace(list_tools=list_tools))
        monkeypatch.setattr("phoxtail.mcp.register_tools", lambda: None)

        from phoxtail.agent.tools import tools_for_caller

        asyncio.run(tools_for_caller())
        asyncio.run(tools_for_caller())
        assert len(calls) == 2, "a cache here would serve one caller's tools to another"


class TestTheAgentCarriesNoMcpTools:
    """Proved against a real agent run rather than by reading the call.

    A `FunctionModel` reports the tools it was offered, so this asks the
    agent itself what a caller would see instead of trusting the wiring.
    """

    @staticmethod
    def _agent_and_seen():
        from pydantic_ai import Agent
        from pydantic_ai.messages import ModelResponse, TextPart
        from pydantic_ai.models.function import AgentInfo, FunctionModel

        seen = []

        def capture(messages, info: AgentInfo):
            seen.append(sorted(t.name for t in info.function_tools))
            return ModelResponse(parts=[TextPart("ok")])

        return Agent(model=FunctionModel(capture)), seen

    def test_a_run_sees_only_the_tools_it_was_given(self):
        from pydantic_ai.toolsets import FunctionToolset

        def alice_only() -> str:
            """Alice may."""
            return "a"

        def bob_only() -> str:
            """Bob may."""
            return "b"

        agent, seen = self._agent_and_seen()
        asyncio.run(agent.run("hi", toolsets=[FunctionToolset(tools=[alice_only])]))
        asyncio.run(agent.run("hi", toolsets=[FunctionToolset(tools=[bob_only])]))

        assert seen[0] == ["alice_only"]
        assert seen[1] == ["bob_only"]

    def test_anything_built_into_the_agent_reaches_every_caller(self):
        """The failure mode, demonstrated rather than described.

        pydantic-ai *adds* a run's toolsets to the agent's own, so a tool
        on the agent is offered to everyone. That is why the MCP tools
        were taken off it — and this is what a future "simplification"
        putting them back would have to explain.
        """
        from pydantic_ai import Agent
        from pydantic_ai.messages import ModelResponse, TextPart
        from pydantic_ai.models.function import AgentInfo, FunctionModel
        from pydantic_ai.toolsets import FunctionToolset

        seen = []

        def capture(messages, info: AgentInfo):
            seen.append(sorted(t.name for t in info.function_tools))
            return ModelResponse(parts=[TextPart("ok")])

        def baked_in() -> str:
            """On the agent, so on every run."""
            return "x"

        def alice_only() -> str:
            """Alice may."""
            return "a"

        agent = Agent(model=FunctionModel(capture), tools=[baked_in])
        asyncio.run(agent.run("hi", toolsets=[FunctionToolset(tools=[alice_only])]))
        assert seen[0] == ["alice_only", "baked_in"]

    def test_the_chatbots_agent_is_built_with_no_mcp_tools(self):
        """Read from the source, because the wiring is what is at stake.

        Building a real agent needs a configured provider; what is
        asserted is the one line that decides whose tools an agent
        carries.
        """
        import inspect

        from phoxtail.agent import llm

        source = inspect.getsource(llm._build_agent)
        assert "tools=get_chat_block_tools()" in source
        assert "get_tools()" not in source


def test_the_old_process_wide_cache_is_gone():
    """Named explicitly, because its absence is the fix.

    ``prime_tools`` filled a module-level list once per process.
    Reintroducing it under any name would restore the bug silently, so
    its absence is asserted rather than assumed.
    """
    from phoxtail.agent import tools

    assert not hasattr(tools, "prime_tools")
    assert not hasattr(tools, "_mcp_tools")
    assert not hasattr(tools, "get_tools")


@pytest.mark.django_db
def test_the_turn_hands_its_toolset_to_the_run():
    """The wiring in chat.py, which no unit test reaches.

    The turn must both act as the person and give the run their tools;
    doing one without the other is a half-fix that looks complete.
    """
    import inspect

    from phoxtail.agent.api.v1 import chat

    source = inspect.getsource(chat._run_turn)
    assert "acting_as(conversation.user)" in source
    assert "toolset_for_caller()" in source
    assert "toolsets=[toolset]" in source
