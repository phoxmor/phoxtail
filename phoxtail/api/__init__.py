"""Phoxtail API — the single HTTP surface for every Phoxtail app.

This package is the API counterpart to the app packages at the top level
(``phoxtail/streams/``, ``phoxtail/design/``, ``phoxtail/booking/``, ...).
Core domains (``streams``, ``content``) ship their routers here; every
optional app that declares ``api_version_router`` on its
``PhoxtailAppConfig`` is auto-mounted at ``/api/<short_label>/v1/``
after Django's app registry is ready.

URL shape:

    /api/streams/v1/...     — core studio API (block variants, collections)
    /api/content/v1/...     — core content API (pages, sites, locales)
    /api/<label>/v1/...     — contributed by any optional app

Per-app versioning means ``streams`` can ship a v2 without dragging every
other app along. Adding a new core domain is a two-line change in this
file; adding a new app-contributed surface requires no changes here at
all — the app declares its router on its ``PhoxtailAppConfig``.
"""

from __future__ import annotations

import importlib

from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from ninja import NinjaAPI
from ninja.security import SessionAuth

from phoxtail.api.auth import Authorize, is_superuser
from phoxtail.api.content.v1 import router as content_v1_router
from phoxtail.api.design.v1 import router as design_v1_router
from phoxtail.api.streams.v1 import router as streams_v1_router
from phoxtail.tokens.ninja import PhoxtailTokenAuth
from phoxtail.users.api.v1 import router as users_v1_router

# Swagger UI and the OpenAPI schema are development conveniences only; in
# production they leak the endpoint surface with no runtime consumer, so we
# close both when DEBUG is off. Passing ``openapi_url=None`` disables the
# schema, which also disables the docs UI that renders it.
_docs_enabled = bool(getattr(settings, "DEBUG", False))

api = NinjaAPI(
    title="Phoxtail API",
    version="1.0.0",
    description=(
        "HTTP API for Phoxtail apps. Consumed by the `phoxtail` CLI, the "
        "Phoxtail MCP server, and (from Phase 5 onwards) by other Phoxtail "
        "projects acting as sync remotes."
    ),
    urls_namespace="phoxtail_api",
    docs_url="/docs/" if _docs_enabled else None,
    openapi_url="/openapi.json" if _docs_enabled else None,
    # Default-deny: every endpoint requires authentication unless it explicitly
    # opts out with ``auth=None``. Token auth is tried first (CLI, MCP); session
    # auth is the fallback for browser clients (e.g. the phoxtail bar).
    auth=[PhoxtailTokenAuth(), SessionAuth()],
)

api.add_router("/streams/v1/", streams_v1_router, tags=["streams/v1"])
api.add_router("/content/v1/", content_v1_router, tags=["content/v1"])
api.add_router("/design/v1/", design_v1_router, tags=["design/v1"])

# The users surface is superuser-only until scoped tokens land: the same
# authenticators as everywhere else, wrapped with an authorization predicate.
# Reads included — loosening reads later is a deliberate decision, not a
# default.
_superuser_detail = "The users API requires an active superuser account."
api.add_router(
    "/users/v1/",
    users_v1_router,
    auth=[
        Authorize(PhoxtailTokenAuth(), is_superuser, detail=_superuser_detail),
        Authorize(SessionAuth(), is_superuser, detail=_superuser_detail),
    ],
    tags=["users/v1"],
)


@api.get("/ping/", tags=["meta"], summary="Authenticated connectivity check")
def ping(request):
    return {"ok": True}


@api.exception_handler(DjangoValidationError)
def handle_django_validation_error(request, exc: DjangoValidationError):
    """Translate service-layer ``ValidationError`` into a 422 response.

    The service layer pattern (``services/admin/operations/*.py`` across
    every Phoxtail app) raises Django's ``ValidationError`` for business-rule
    violations — a convention built around Django forms/views, which convert
    it to form errors automatically. Ninja has no such conversion built in,
    so left uncaught this becomes an unhandled 500. Registered on the shared
    ``api`` instance, this applies to every contributed router automatically.
    """
    return api.create_response(request, {"detail": exc.messages}, status=422)


# Core router short labels — contributors cannot reuse these, or they
# would shadow a core domain.
_CORE_SHORT_LABELS = frozenset({"streams", "content", "design", "pages", "users"})


def _short_label(config) -> str:
    """Strip the ``phoxtail_`` prefix from an app label for URL scoping.

    ``phoxtail_blog`` → ``blog``. Apps whose label does not start with
    ``phoxtail_`` use the label verbatim.
    """
    return config.label.removeprefix("phoxtail_")


def collect_contributed_routers():
    """Yield ``(short_label, router)`` for every contributed app router.

    Walks ``django_apps.get_app_configs()``, filters to
    ``PhoxtailAppConfig`` instances with ``api_version_router`` set, and
    imports the dotted path. Collisions with a core short label raise
    ``RuntimeError``.
    """
    from django.apps import apps as django_apps

    from phoxtail.core.app_config import PhoxtailAppConfig

    seen: set[str] = set()
    for config in django_apps.get_app_configs():
        if not isinstance(config, PhoxtailAppConfig):
            continue
        dotted = config.api_version_router
        if not dotted:
            continue
        short = _short_label(config)
        if short in _CORE_SHORT_LABELS:
            raise RuntimeError(
                f"App '{config.label}' tries to mount /api/{short}/v1/ but that namespace is reserved by a core domain."
            )
        if short in seen:
            raise RuntimeError(f"Two apps both try to mount /api/{short}/v1/.")
        module_path, _, attr = dotted.rpartition(".")
        sub_router = getattr(importlib.import_module(module_path), attr)
        seen.add(short)
        yield short, sub_router


_contributed_mounted = False


def mount_contributed_routers() -> None:
    """Mount every contributed ``api_version_router`` onto the shared API.

    Idempotent — safe to call multiple times (a second call is a no-op).
    Invoked by ``PhoxtailCoreConfig.ready()`` so the mount happens
    exactly once, after Django's app registry is fully populated.
    Callers who import ``phoxtail.api`` before ``django.setup()``
    (unusual) will not see contributed routers until ``ready()`` fires.
    """
    global _contributed_mounted
    if _contributed_mounted:
        return
    for short, sub_router in collect_contributed_routers():
        api.add_router(f"/{short}/v1/", sub_router, tags=[f"{short}/v1"])
    _contributed_mounted = True
