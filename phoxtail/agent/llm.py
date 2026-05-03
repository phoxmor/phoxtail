"""PydanticAI agent factory for the Phoxtail chatbot."""

from __future__ import annotations

import os

from pydantic_ai import Agent
from pydantic_ai.models.google import GoogleModel

from .tools import get_tools

_agent: Agent | None = None


def get_agent() -> Agent:
    global _agent
    if _agent is None:
        model_name = os.environ.get("PHOXTAIL_CHATBOT_MODEL", "gemini-2.5-flash")
        model = GoogleModel(model_name)
        _agent = Agent(model=model, tools=get_tools())
    return _agent
