"""v1 of the users API.

Aggregates the users sub-routers into the single ``Router`` this app offers
as its ``v1``, served at ``/api/users/v1/``. Each endpoint names the
permission its own act requires, so the mount decides nothing.
"""

from __future__ import annotations

from ninja import Router

from phoxtail.users.api.v1.genders import router as genders_router
from phoxtail.users.api.v1.users import router as users_router

router = Router()

router.add_router("/users", users_router)
router.add_router("/genders", genders_router)
