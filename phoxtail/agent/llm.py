"""PydanticAI agent factory for the Phoxtail chatbot."""

import os
from functools import lru_cache

from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from .models import ModelArtifact
from .tools import get_tools


@lru_cache(maxsize=16)
def _build_agent(
    model_prefix: str,
    identifier: str,
    base_url: str | None,
    api_key_env_var: str | None,
    cache_key: str,  # updated_at timestamps — forces rebuild after admin edits
) -> Agent:
    api_key = os.environ.get(api_key_env_var) if api_key_env_var else None

    if base_url:
        model = OpenAIChatModel(
            identifier,
            provider=OpenAIProvider(base_url=base_url, api_key=api_key or "EMPTY"),
        )
    else:
        # pydantic-ai accepts "<prefix>:<identifier>" model strings directly.
        model = f"{model_prefix}:{identifier}" if model_prefix else identifier

    return Agent(model=model, tools=get_tools())


def get_agent(artifact: ModelArtifact) -> Agent:
    provider = artifact.provider
    return _build_agent(
        model_prefix=provider.model_prefix or "",
        identifier=artifact.identifier,
        base_url=provider.base_url or None,
        api_key_env_var=provider.api_key_env_var or None,
        cache_key=(
            f"{provider.updated_at.timestamp()}|{artifact.updated_at.timestamp()}"
        ),
    )
