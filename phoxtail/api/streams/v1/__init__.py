"""v1 of the streams API.

Builds a single ``Router`` that aggregates every resource in this version
(variants, collections, blocks, prompts). The aggregate router is mounted
at ``/api/streams/v1/`` by ``phoxtail.api``.
"""

from __future__ import annotations

from ninja import Router

from phoxtail.api.streams.v1.blocks import router as blocks_router
from phoxtail.api.streams.v1.collections import router as collections_router
from phoxtail.api.streams.v1.prompts import router as prompts_router
from phoxtail.api.streams.v1.variants import router as variants_router

router = Router()
router.add_router("/variants", variants_router)
router.add_router("/collections", collections_router)
router.add_router("/blocks", blocks_router)
router.add_router("/prompts", prompts_router)
