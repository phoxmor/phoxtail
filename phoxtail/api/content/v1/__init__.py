"""v1 of the content API.

Aggregates the generic sub-routers into a single ``Router`` mounted at
``/api/content/v1/`` by ``phoxtail.api``.

App-specific endpoints (e.g. blog's ``/authors/``) do **not** live under
this prefix — each app owns its own ``/api/<short_label>/v1/`` namespace
and contributes into the content domain only through the
``page_schema_contributors`` registry in :mod:`contrib`.
"""

from __future__ import annotations

from ninja import Router

from phoxtail.api.content.v1.blocks import router as blocks_router
from phoxtail.api.content.v1.body import router as body_router
from phoxtail.api.content.v1.collections import router as collections_router
from phoxtail.api.content.v1.locales import router as locales_router
from phoxtail.api.content.v1.page_types import router as page_types_router
from phoxtail.api.content.v1.pages import router as pages_router
from phoxtail.api.content.v1.sites import router as sites_router

router = Router()
# /pages/ and /pages/{id}/* live on pages_router.
router.add_router("/pages", pages_router)
# Body endpoints: /pages/{id}/body/...
router.add_router("/pages", body_router)
# Per-block endpoints: /pages/{id}/blocks/...
router.add_router("/pages", blocks_router)
router.add_router("/collections", collections_router)
router.add_router("/page-types", page_types_router)
router.add_router("/locales", locales_router)
router.add_router("/sites", sites_router)
