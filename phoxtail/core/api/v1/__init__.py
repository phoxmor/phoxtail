"""v1 of the core API.

InternalLink — the snippet other apps point at when they need a link to
somewhere inside the platform.
"""

from __future__ import annotations

from ninja import Router

from phoxtail.core.api.v1.internal_links import router as internal_links_router

router = Router()
router.add_router("/internal-links", internal_links_router)
