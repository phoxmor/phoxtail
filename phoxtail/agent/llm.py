"""PydanticAI agent factory for the Phoxtail chatbot."""

from __future__ import annotations

import os
from functools import lru_cache
from typing import TYPE_CHECKING

from .chat_blocks import get_chat_block_tools
from .models import ModelArtifact

if TYPE_CHECKING:
    from pydantic_ai import Agent


@lru_cache(maxsize=16)
def _build_agent(
    model_prefix: str,
    identifier: str,
    base_url: str | None,
    api_key_env_var: str | None,
    cache_key: str,  # updated_at timestamps — forces rebuild after admin edits
) -> Agent:
    # Imported here, not at module level: this module loads at django.setup()
    # via the chat router, and pydantic_ai costs ~50MB RSS per process. Only
    # a process that actually runs a chat turn should pay that.
    from pydantic_ai import Agent
    from pydantic_ai.models.openai import OpenAIChatModel
    from pydantic_ai.providers.openai import OpenAIProvider

    api_key = os.environ.get(api_key_env_var) if api_key_env_var else None

    model: OpenAIChatModel | str
    if base_url:
        model = OpenAIChatModel(
            identifier,
            provider=OpenAIProvider(base_url=base_url, api_key=api_key or "EMPTY"),
        )
    else:
        # pydantic-ai accepts "<prefix>:<identifier>" model strings directly.
        model = f"{model_prefix}:{identifier}" if model_prefix else identifier

    return Agent(
        model=model,
        # Only the tools that are the same for everyone. The MCP tools are
        # not: what a person may be offered depends on the credential
        # their turn carries, and this agent is memoised per model and
        # shared by every caller using it. They are handed to the run
        # instead — see `toolset_for_caller`.
        tools=get_chat_block_tools(),
    )


async def get_agent(artifact: ModelArtifact) -> Agent:
    provider = artifact.provider
    return _build_agent(
        model_prefix=provider.model_prefix or "",
        identifier=artifact.identifier,
        base_url=provider.base_url or None,
        api_key_env_var=provider.api_key_env_var or None,
        cache_key=(f"{provider.updated_at.timestamp()}|{artifact.updated_at.timestamp()}"),
    )
