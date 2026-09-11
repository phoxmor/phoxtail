"""Authorization wrappers for the shared Phoxtail API.

Authentication (who are you) is handled by the backends on the shared
``NinjaAPI`` instance — ``PhoxtailTokenAuth`` and :class:`PhoxtailSessionAuth`,
both of which resolve an
:class:`~phoxtail.core.authorization.AuthorizationContext`. Authorization
(are you allowed) is layered on top by composition: :class:`Authorize`
wraps an authenticator and applies a predicate to the caller it resolves.

Predicates take the whole context, not just the user, so the same wrapper
becomes the seam for scope enforcement
(``predicate=has_scope("phoxtail_users.change_user")``) without touching
the authentication backends — a token narrows its owner, so answering
that question needs both halves.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ninja.errors import HttpError
from ninja.security import SessionAuth

from phoxtail.core.authorization import AuthorizationContext
from phoxtail.tokens.ninja import PhoxtailTokenAuth


class Refused(Exception):
    """A predicate declining, in its own words.

    A predicate normally answers yes or no and :class:`Authorize` supplies
    the message. One that can distinguish *why* raises this instead, and
    the wrapper uses its text — so a caller learns whether to widen their
    credential or to go and be granted a permission.
    """


class PhoxtailSessionAuth(SessionAuth):
    """Ninja's session auth, resolving the same shape as token auth.

    A browser session has no credential to narrow the user by, so the
    context carries ``token=None``. Without this wrapper endpoints would
    have to handle two different ``request.auth.user`` shapes depending on how
    the caller happened to log in.
    """

    def authenticate(self, request, key):
        user = super().authenticate(request, key)
        if not user:
            return None
        return AuthorizationContext(user=user)


class Authorize:
    """Wrap an authenticator with an authorization predicate.

    Delegates authentication to the wrapped backend. If the backend
    resolves no caller, returns ``None`` so ninja continues down the auth
    stack (and ultimately responds 401). If the backend resolves a caller
    that fails the predicate, raises ``HttpError(403)`` — authenticated
    but forbidden — so agents can distinguish a bad token from a missing
    privilege.
    """

    def __init__(
        self,
        authenticator: Callable[..., Any],
        predicate: Callable[[Any], bool],
        detail: str = "You do not have permission to perform this action.",
    ) -> None:
        self.authenticator = authenticator
        self.predicate = predicate
        self.detail = detail

    def __call__(self, request):
        context = self.authenticator(request)
        if not context:
            return None
        try:
            permitted = self.predicate(context)
        except Refused as refusal:
            # The predicate knew something this wrapper does not: which of
            # the two halves failed. Saying so is the difference between
            # "widen your token" and "ask an administrator", which are not
            # the same instruction and cannot be told apart from a shared
            # message. A predicate that simply returns False is unchanged
            # and still refuses with ``detail``.
            raise HttpError(403, str(refusal)) from None
        if not permitted:
            raise HttpError(403, self.detail)
        return context

    def __getattr__(self, name):
        # ninja probes auth callbacks for metadata (openapi_security_schema,
        # csrf, ...); forward those lookups so wrapping stays transparent.
        return getattr(self.authenticator, name)


def is_superuser(context) -> bool:
    """Predicate for surfaces restricted to active superusers."""
    user = context.user
    return bool(user.is_active and user.is_superuser)


def has_no_ceiling(context) -> bool:
    """Whether the caller brought no self-imposed limit.

    True for a browser session (nothing to narrow) and for an unrestricted
    token. False for a token carrying scopes — which is what makes an
    endpoint that declares no scope unreachable to one.
    """
    token = context.token
    return token is None or token.unrestricted


def has_scope(*codenames: str) -> Callable[[Any], bool]:
    """Predicate: the caller's credential permits *all* of *codenames*.

    A session has no credential to narrow by and passes; so does an
    unrestricted token. A scoped token must name every codename asked
    for — a partial match is a refusal, since the endpoint declared what
    it needs and half of it is not it.

    This is only the credential's half of the question. Whether the
    *person* may act is decided where it already is, and often far more
    finely than a codename can express.
    """

    def predicate(context) -> bool:
        if has_no_ceiling(context):
            return True
        return all(codename in context.token.scopes for codename in codenames)

    return predicate


def has_permission(*codenames: str) -> Callable[[Any], bool]:
    """Predicate: the *person* holds all of *codenames*.

    The other half of the question :func:`has_scope` asks. A credential
    can only ever narrow its owner, so this is what establishes there was
    something to narrow — without it a token naming a codename would grant
    it, and minting deliberately does not require the minter to hold what
    they name (see ``phoxtail.tokens.scopes``).

    Superusers pass, as they do everywhere in Django.

    **Only for permissions Django answers globally.** Where an app decides
    per object — Wagtail grants ``publish_page`` per page subtree, through
    ``GroupPagePermission`` rows that ``has_perm`` never reads — this
    returns ``False`` for someone genuinely allowed. Those endpoints ask
    their own authority, in the body, where the object is known.
    """

    def predicate(context) -> bool:
        # Every backend resolves a context around a real user or returns
        # None instead, so there is no authenticated caller without one.
        user = context.user
        if not user.is_active:
            return False
        return all(user.has_perm(codename) for codename in codenames)

    return predicate


def guarded(*codenames: str) -> list[Authorize]:
    """The ``auth=`` for an endpoint, naming the codename of its act once.

    Used as ``auth=guarded("phoxtail_dashboard.delete_menu")``. Both halves
    of authorization are asked of the same codename:

    1. may this *person* act — their Django permissions;
    2. may this *credential* be used for it — the token's scopes, where a
       session or an unrestricted token carries no ceiling.

    Both must pass. The two refusals are not the same event and do not
    share a message: a narrowed credential is the system working, and its
    owner can mint a wider one; a missing permission is not theirs to fix.

    Writing the codename once is the point. The endpoint's permission and
    the scope its MCP tool names must agree, and the surest way for two
    things to agree is for there to be one of them.

    Where the permission is finer than a codename, use :func:`scoped` and
    ask the finer authority inside the endpoint — see
    :func:`has_permission`.

    Takes no ``detail``, where :func:`scoped` does: this predicate always
    declines in its own words, so there is no message left for the wrapper
    to supply.
    """

    def predicate(context) -> bool:
        if not has_permission(*codenames)(context):
            raise Refused("Your account does not have permission to " + ", ".join(codenames) + ".")
        if not has_scope(*codenames)(context):
            raise Refused("This token's scopes do not cover " + ", ".join(codenames) + ".")
        return True

    return [
        Authorize(PhoxtailTokenAuth(), predicate),
        Authorize(PhoxtailSessionAuth(), predicate),
    ]


def scoped(*codenames: str, detail: str | None = None) -> list[Authorize]:
    """The ``auth=`` for an endpoint a scoped token may reach.

    Used as ``auth=scoped("wagtailcore.publish_page")``. Endpoints that
    declare nothing keep the API-wide default, which admits sessions and
    unrestricted tokens and refuses scoped ones — so forgetting to
    annotate leaves a door closed rather than open.
    """
    if detail is None:
        detail = "This token's scopes do not cover " + ", ".join(codenames) + "."
    predicate = has_scope(*codenames)
    return [
        Authorize(PhoxtailTokenAuth(), predicate, detail=detail),
        Authorize(PhoxtailSessionAuth(), predicate, detail=detail),
    ]
