"""v1 of the dashboard API.

Aggregates the dashboard's resources into a single ``Router``, contributed
to the auto-mount machinery at ``/api/dashboard/v1/`` by
``PhoxtailDashboardConfig``.
"""

from __future__ import annotations

from ninja import Router

from phoxtail.dashboard.api.v1.menus import router as menus_router

router = Router()
router.add_router("/menus", menus_router)
