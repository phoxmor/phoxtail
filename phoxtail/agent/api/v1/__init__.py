"""v1 of the agent API.

Mounted automatically at ``/api/agent/v1/`` via
``PhoxtailAgentConfig.api_version_router``.
"""

from __future__ import annotations

from ninja import Router
from ninja.security import django_auth

from phoxtail.agent.api.v1.chat import router as chat_router

router = Router(auth=django_auth)
router.add_router("/", chat_router)
