"""v1 of the streams API.

Builds a single ``Router`` that aggregates every resource in this version
(variants, collections, blocks, context). The aggregate router is mounted
at ``/api/streams/v1/`` by ``phoxtail.api``.
"""

from __future__ import annotations

from ninja import Router

from phoxtail.api.streams.v1.block_categories import assignment_router as block_category_assignment_router
from phoxtail.api.streams.v1.block_categories import router as block_categories_router
from phoxtail.api.streams.v1.blocks import router as blocks_router
from phoxtail.api.streams.v1.collections import router as collections_router
from phoxtail.api.streams.v1.context import router as context_router
from phoxtail.api.streams.v1.schema_catalog import router as schema_catalog_router
from phoxtail.api.streams.v1.shared_blocks import router as shared_blocks_router
from phoxtail.api.streams.v1.variants import router as variants_router

router = Router()
router.add_router("/variants", variants_router)
router.add_router("/collections", collections_router)
router.add_router("/blocks", blocks_router)
router.add_router("/blocks", block_category_assignment_router)
router.add_router("/block-categories", block_categories_router)
router.add_router("/context", context_router)
router.add_router("/schema-catalog", schema_catalog_router)
router.add_router("/shared-blocks", shared_blocks_router)
