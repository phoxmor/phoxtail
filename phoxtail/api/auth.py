"""Authorization wrappers for the shared Phoxtail API.

Authentication (who are you) is handled by the backends on the shared
``NinjaAPI`` instance — ``PhoxtailTokenAuth`` and ``SessionAuth``, both of
which resolve a real ``User``. Authorization (are you allowed) is layered
on top by composition: :class:`Authorize` wraps an authenticator and
applies a predicate to the user it resolves.

Keeping the two concerns separate means the same wrapper becomes the seam
for future scope enforcement (``predicate=has_scope("users:write")``)
without touching the authentication backends.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ninja.errors import HttpError


class Authorize:
    """Wrap an authenticator with an authorization predicate.

    Delegates authentication to the wrapped backend. If the backend
    resolves no user, returns ``None`` so ninja continues down the auth
    stack (and ultimately responds 401). If the backend resolves a user
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
        user = self.authenticator(request)
        if not user:
            return None
        if not self.predicate(user):
            raise HttpError(403, self.detail)
        return user

    def __getattr__(self, name):
        # ninja probes auth callbacks for metadata (openapi_security_schema,
        # csrf, ...); forward those lookups so wrapping stays transparent.
        return getattr(self.authenticator, name)


def is_superuser(user) -> bool:
    """Predicate for surfaces restricted to active superusers."""
    return bool(user.is_active and user.is_superuser)
