"""Phoxtail API — the single HTTP surface for every Phoxtail app.

This package is the API counterpart to the app packages at the top level
(``phoxtail/streams/``, ``phoxtail/design/``, ``phoxtail/booking/``, ...).
Core domains (``streams``, ``pages``) ship their routers here; every
optional app that declares ``api_version_router`` on its
``PhoxtailAppConfig`` is auto-mounted at ``/api/<short_label>/v1/``
after Django's app registry is ready.

URL shape:

    /api/streams/v1/...     — core studio API
    /api/pages/v1/...       — core pages API (generic Wagtail surface)
    /api/<label>/v1/...     — contributed by any optional app

Per-app versioning means ``streams`` can ship a v2 without dragging every
other app along. Adding a new core domain is a two-line change in this
file; adding a new app-contributed surface requires no changes here at
all — the app declares its router on its ``PhoxtailAppConfig``.
"""

from __future__ import annotations

import importlib

from django.conf import settings
from ninja import NinjaAPI

from phoxtail.api.pages.v1 import router as pages_v1_router
from phoxtail.api.streams.v1 import router as streams_v1_router
from phoxtail.tokens.ninja import PhoxtailTokenAuth

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
    # Default-deny: every endpoint requires a valid AccessToken unless it
    # explicitly opts out with ``auth=None``. Routes can still override this
    # per-endpoint, but the safe posture is enforced by default.
    auth=PhoxtailTokenAuth(),
)

api.add_router("/streams/v1/", streams_v1_router, tags=["streams/v1"])
api.add_router("/pages/v1/", pages_v1_router, tags=["pages/v1"])


# Core router short labels — contributors cannot reuse these, or they
# would shadow a core domain.
_CORE_SHORT_LABELS = frozenset({"streams", "pages"})


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
                f"App '{config.label}' tries to mount /api/{short}/v1/ "
                f"but that namespace is reserved by a core domain."
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
