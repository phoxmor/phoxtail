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
        if not self.predicate(context):
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
