"""v1 of the agent API.

Mounted automatically at ``/api/agent/v1/`` via
``PhoxtailAgentConfig.api_version_router``.
"""

from __future__ import annotations

from ninja import Router
from ninja.security import django_auth

from phoxtail.agent.api.v1.artifacts import router as artifacts_router
from phoxtail.agent.api.v1.chat import router as chat_router
from phoxtail.agent.api.v1.providers import router as providers_router
from phoxtail.agent.api.v1.settings import router as settings_router

router = Router()

# Chat is browser-only SSE; the rest inherits the shared API auth stack.
router.add_router("/", chat_router, auth=django_auth)
router.add_router("/providers", providers_router)
router.add_router("/artifacts", artifacts_router)
router.add_router("/settings", settings_router)
