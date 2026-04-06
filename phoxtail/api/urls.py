"""URL entrypoint for the Phoxtail API.

A hatched project mounts this module at ``/api/``:

    path("api/", include("phoxtail.api.urls"))

All routers for every app (streams/v1, design/v1, booking/v1, ...) are
registered on the single ``NinjaAPI`` instance in ``phoxtail.api``.
"""

from __future__ import annotations

from django.urls import path

from phoxtail.api import api

urlpatterns = [
    path("", api.urls),
]
