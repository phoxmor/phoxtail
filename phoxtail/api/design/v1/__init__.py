"""v1 of the design API.

Aggregates design sub-routers into a single ``Router`` mounted at
``/api/design/v1/`` by ``phoxtail.api``.
"""

from __future__ import annotations

from ninja import Router

from phoxtail.api.design.v1.font_families import router as font_families_router
from phoxtail.api.design.v1.font_roles import router as font_roles_router
from phoxtail.api.design.v1.font_weights import router as font_weights_router
from phoxtail.api.design.v1.palette_roles import router as palette_roles_router
from phoxtail.api.design.v1.palette_sets import router as palette_sets_router
from phoxtail.api.design.v1.palettes import router as palettes_router

router = Router()
router.add_router("/palette-sets", palette_sets_router)
router.add_router("/palettes", palettes_router)
router.add_router("/palette-roles", palette_roles_router)
router.add_router("/font-families", font_families_router)
router.add_router("/font-weights", font_weights_router)
router.add_router("/font-roles", font_roles_router)
