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
from datetime import datetime
from uuid import UUID

from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from ninja import NinjaAPI, Schema

from phoxtail.api.auth import Authorize, PhoxtailSessionAuth, has_no_ceiling, is_superuser
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

# Names the reason rather than the rule: a caller who deliberately narrowed
# their token needs to know the endpoint has not opted in yet, not to be
# told again what a scope is.
_undeclared_detail = (
    "This endpoint declares no scope, so a token carrying scopes cannot reach "
    "it. Use an unrestricted token, or add auth=scoped(...) to the endpoint."
)

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
    #
    # An endpoint that declares no scope is reachable by sessions and
    # unrestricted tokens — everything that works today — and refuses a
    # token carrying a ceiling. Endpoints opt in with ``auth=scoped(...)``,
    # so forgetting to annotate one leaves a door closed rather than open.
    auth=[
        Authorize(PhoxtailTokenAuth(), has_no_ceiling, detail=_undeclared_detail),
        PhoxtailSessionAuth(),
    ],
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
        Authorize(PhoxtailSessionAuth(), is_superuser, detail=_superuser_detail),
    ],
    tags=["users/v1"],
)


@api.get("/ping/", tags=["meta"], summary="Authenticated connectivity check")
def ping(request):
    return {"ok": True}


class WhoAmI(Schema):
    """What a caller is, as this project sees them."""

    # The address, not the `username` column. `USERNAME_FIELD` is `email`
    # here, so the email is what a person signs in with and what names
    # them in an audit line; the inherited `username` column is left
    # empty by `create_user` and identifies nobody.
    email: str
    # Users are addressed by uuid everywhere else the API and the MCP
    # tools name one, so a caller can use this answer as an argument.
    user_uuid: UUID
    is_superuser: bool
    # False means the credential carries a ceiling and ``scopes`` lists it.
    # True means it carries none; ``scopes`` is then empty and meaningless.
    unrestricted: bool
    scopes: list[str]
    # None for a browser session, which has no credential to expire.
    expires_at: datetime | None


@api.get(
    "/whoami/",
    response=WhoAmI,
    tags=["meta"],
    summary="The identity and ceiling of the current credential",
    # The one endpoint that must admit every credential, including narrowly
    # scoped ones: a caller cannot discover its own limits if the endpoint
    # that reports them is behind those limits. Declared explicitly rather
    # than inheriting, because the API-wide default refuses scoped tokens.
    auth=[PhoxtailTokenAuth(), PhoxtailSessionAuth()],
)
def whoami(request):
    """Answer "who is this, and what may they do" for the caller's own token.

    Exists for callers that hold a credential without being able to read
    it — the MCP server forwards an opaque Bearer and is, by design, never
    the authority on what it contains. Asking the authority is how it
    learns; deciding for itself is what it must never do.

    Reports the credential's ceiling, not the person's permissions. What
    the *user* may do is answered per action, where the action happens,
    and is often finer than any list could be.
    """
    context = request.auth
    token = context.token
    return {
        "email": context.user.email,
        "user_uuid": context.user.uuid,
        "is_superuser": bool(context.user.is_superuser),
        "unrestricted": token is None or bool(token.unrestricted),
        "scopes": list(token.scopes) if token is not None else [],
        "expires_at": token.expires_at if token is not None else None,
    }


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
