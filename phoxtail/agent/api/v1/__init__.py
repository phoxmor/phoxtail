"""v1 of the agent API.

Mounted at ``/api/agent/v1/``. This app has not moved to the ``<pkg>/api/``
convention yet: its surface is gated on whether the chatbot's optional
dependency is installed, and that gate has nowhere to live under a convention
that reads only whether a module exists.
"""

from __future__ import annotations

from ninja import Router

from phoxtail.agent.api.v1.artifacts import router as artifacts_router
from phoxtail.agent.api.v1.chat import router as chat_router
from phoxtail.agent.api.v1.providers import router as providers_router
from phoxtail.agent.api.v1.settings import router as settings_router
from phoxtail.api.auth import PhoxtailSessionAuth

router = Router()

# Chat is browser-only SSE; the rest inherits the shared API auth stack.
# Not ninja's stock django_auth: it resolves a bare User, and every endpoint
# in phoxtail reads request.auth as an AuthorizationContext.
router.add_router("/", chat_router, auth=PhoxtailSessionAuth())
router.add_router("/providers", providers_router)
router.add_router("/artifacts", artifacts_router)
router.add_router("/settings", settings_router)
