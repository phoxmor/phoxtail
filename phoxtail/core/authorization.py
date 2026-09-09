"""The authenticated caller.

Authentication answers two questions, not one: *who are you* and *how did
you get in*. Phoxtail used to answer only the first — every auth backend
resolved a ``User`` and discarded the credential, so no layer downstream
could ask what the caller had actually presented. A token's scopes, type
and expiry existed for the length of one function call and were thrown
away at the door.

:class:`AuthorizationContext` is what backends resolve instead. It is the
single shape every authentication path produces — personal tokens today,
OAuth tokens and session logins alongside them — so that authorization
has one thing to reason about however the caller arrived.

It deliberately holds no policy. "May this caller do X" belongs to the
three layers described in the *Authorization Layers* pattern; this object
only makes the facts those layers need reachable.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover - typing only
    from phoxtail.tokens.models import AccessToken


@dataclass(frozen=True)
class AuthorizationContext:
    """Who is making this request, and with what credential.

    ``token`` is ``None`` for a browser session, where the caller is the
    person directly and there is no delegated credential to narrow them.
    A token, when present, can only ever *narrow* what its owner may do —
    it never grants anything the user does not already have.
    """

    user: Any
    token: AccessToken | None = None
