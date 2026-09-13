"""Phoxtail API — the single HTTP surface for every Phoxtail app.

The ``NinjaAPI`` instance lives here, along with the project-wide concerns
that belong to no single app: the authentication defaults, ``/ping/``,
``/whoami/``, and the exception handler every router inherits.

Which routers are mounted is not decided here. An app that subclasses
``PhoxtailAppConfig`` and ships ``<pkg>/api/`` declaring ``versions`` is
mounted at ``/api/<name>/<version>/`` once the app registry is ready, where
``name`` is its label without the ``phoxtail_`` prefix. See
:mod:`phoxtail.core.discovery`.

URL shape::

    /api/<name>/v1/...   — one app's surface, versioned on its own

Per-app versioning means one app can ship a v2 without dragging every other
app along. Adding a surface needs no change to this file at all.
"""

from __future__ import annotations

import re
from datetime import datetime
from uuid import UUID

from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from ninja import NinjaAPI, Schema

from phoxtail.api.auth import Authorize, PhoxtailSessionAuth, has_no_ceiling
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


# Every users endpoint names the permission its act requires, so there is
# nothing left for the mount to say. Kept hand-mounted only until the app
# itself is discovered.
api.add_router("/users/v1/", users_v1_router, tags=["users/v1"])


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


# The one surface still mounted by hand above, because its router carries a
# superuser rule this file applies and the convention has nowhere to put.
# When that rule moves onto its endpoints, users joins the rest and this set
# goes away.
_CORE_SHORT_LABELS = frozenset({"users"})


# A key of `versions` is spliced straight into the URL.
_VERSION_SEGMENT = re.compile(r"v[0-9]+")

_discovered_mounted = False


def mount_discovered_routers() -> None:
    """Mount the HTTP face of every discoverable phoxtail app.

    An app is discoverable by subclassing ``PhoxtailAppConfig``; it is mounted
    by shipping ``<pkg>/api/`` declaring ``versions``. Nothing else is
    consulted — there is no registry to append to and no dotted string to
    declare. See :mod:`phoxtail.core.discovery`.

    Idempotent — safe to call multiple times (a second call is a no-op).
    Invoked by ``PhoxtailCoreConfig.ready()`` so the mount happens exactly
    once, after Django's app registry is fully populated. Callers who import
    ``phoxtail.api`` before ``django.setup()`` (unusual) will not see
    discovered routers until ``ready()`` fires.
    """
    global _discovered_mounted
    if _discovered_mounted:
        return

    from phoxtail.core.discovery import versioned_routers

    seen: set[str] = set()
    for name, versions in versioned_routers():
        if name in _CORE_SHORT_LABELS:
            raise RuntimeError(
                f"App '{name}' tries to mount /api/{name}/ but that namespace is reserved by a core domain."
            )
        if name in seen:
            raise RuntimeError(f"Two apps both try to mount /api/{name}/.")
        seen.add(name)
        for version, sub_router in versions.items():
            # The key becomes a path segment, so a stray space or an empty
            # string mounts a URL nobody can reach and nothing reports. Say so
            # here, where the name is still attached to the app that wrote it.
            if not _VERSION_SEGMENT.fullmatch(version):
                raise RuntimeError(
                    f"App '{name}' declares API version {version!r}, which is not a version segment like 'v1'."
                )
            api.add_router(f"/{name}/{version}/", sub_router, tags=[f"{name}/{version}"])

    _discovered_mounted = True
