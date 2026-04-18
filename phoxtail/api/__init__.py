"""Phoxtail API — the single HTTP surface for every Phoxtail app.

This package is the API counterpart to the app packages at the top level
(``phoxtail/streams/``, ``phoxtail/design/``, ``phoxtail/booking/``, ...).
Each app gets its own sub-package here, and within it one sub-package per
API version (``v1``, ``v2``, ...). Routers are registered on the single
``NinjaAPI`` instance defined below.

URL shape (mounted at ``/api/`` in a hatched project's root urls.py):

    /api/streams/v1/variants
    /api/streams/v1/variants/{identifier}
    /api/streams/v1/collections
    /api/streams/v1/blocks
    /api/streams/v1/prompts
    /api/streams/v1/prompts/{identifier}/render

Per-app versioning means ``streams`` can ship a v2 without dragging every
other app along. Adding a new app is a two-line change in this file.
"""

from __future__ import annotations

from ninja import NinjaAPI

from phoxtail.api.streams.v1 import router as streams_v1_router
from phoxtail.tokens.ninja import PhoxtailTokenAuth

api = NinjaAPI(
    title="Phoxtail API",
    version="1.0.0",
    description=(
        "HTTP API for Phoxtail apps. Consumed by the `phoxtail` CLI, the "
        "Phoxtail MCP server, and (from Phase 5 onwards) by other Phoxtail "
        "projects acting as sync remotes."
    ),
    urls_namespace="phoxtail_api",
    docs_url="/docs/",
    # Default-deny: every endpoint requires a valid AccessToken unless it
    # explicitly opts out with ``auth=None``. Routes can still override this
    # per-endpoint, but the safe posture is enforced by default.
    auth=PhoxtailTokenAuth(),
)

api.add_router("/streams/v1/", streams_v1_router, tags=["streams/v1"])
