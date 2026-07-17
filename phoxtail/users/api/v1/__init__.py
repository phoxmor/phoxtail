"""v1 of the users API.

Builds a single ``Router`` that aggregates every resource in this version
(users, genders). The aggregate router is mounted at ``/api/users/v1/``
by ``phoxtail.api`` behind a superuser-only authorization stack.
"""

from __future__ import annotations

from ninja import Router

from phoxtail.users.api.v1.genders import router as genders_router
from phoxtail.users.api.v1.users import router as users_router

router = Router()

router.add_router("/users", users_router)
router.add_router("/genders", genders_router)
