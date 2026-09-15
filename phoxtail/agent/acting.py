"""The chatbot acting as the person who is chatting.

**The situation this exists for.** A chat turn runs in a background task
inside Django. Nothing arrived over HTTP, so when a tool calls the API,
``outbound_token()`` finds no caller credential to forward and falls back
to the credential stored on this machine. Every person's tool call
therefore ran as whoever last ran ``phoxtail auth login`` in this
container — and because the credential half of every door was answered by
that same stranger, the catalogue collapsed to the handful of tools that
name no permission at all.

Both are one absence: the person is known and brings nothing to present.

**What this adds is the missing credential, not a bypass.** For the length
of one turn the person gets a real ``AccessToken`` of their own — narrow,
short-lived, owned by them — and everything downstream treats it as it
treats any other token. Nothing learns that a chatbot exists: the API
authenticates it the ordinary way, the tool catalogue narrows the ordinary
way, and the audit trail names the person because the person is who it
belongs to.

**Why a token rather than the user object.** Handing tools a ``User``
would answer who, and the filtering asks what a credential permits. The
tool registry reads the credential and nothing else, so a caller carrying
only a name is indistinguishable from one carrying nothing — which is
precisely the state that emptied the catalogue. A name cannot be narrowed,
cannot expire, and cannot be withdrawn from one channel without being
withdrawn from the person.
"""

from __future__ import annotations

import contextlib
from datetime import timedelta

from asgiref.sync import sync_to_async
from django.utils import timezone

from phoxtail.tokens.constants import TokenType

# Long enough that no ordinary turn outlives it, short enough that a leaked
# one is worth little. It is never shown to anyone: it is minted inside the
# turn, spent by that turn's tool calls, and revoked on the way out — so
# this is the bound on a turn that dies without unwinding, not on how long
# a person may hold a key.
TURN_LIFETIME = timedelta(minutes=15)

TOKEN_NAME = "Chat turn"


def mint_turn_credential(user) -> tuple[object, str]:
    """A credential for this person, for this turn.

    Scoped to the permissions the person actually holds, which is not a
    narrowing — the person's own half is asked again at every door and
    answers independently. It is written down because the credential half
    reads a list and cannot read a user, so "everything you may do" has to
    be said in the vocabulary that half understands.

    Deliberately not ``unrestricted``. That flag means *whatever its owner
    may do, including capabilities installed later*, and a credential that
    lives for one exchange has no later. Writing the list at mint time is
    the same reasoning that removed the wildcard: a ceiling that rises on
    its own is not a ceiling.
    """
    from phoxtail.tokens.services import AccessTokenService

    # TextChoices members are plain strings at runtime; without Django stubs
    # a type checker reads the attribute as the (value, label) tuple it was
    # assigned from. Same annotation the token service itself carries.
    chatbot: str = TokenType.CHATBOT  # type: ignore[assignment]
    return AccessTokenService().admin.create(
        user_id=user.pk,
        name=TOKEN_NAME,
        description=f"Minted for one chat turn by {user.email}.",
        scopes=sorted(user.get_all_permissions()),
        expires_at=timezone.now() + TURN_LIFETIME,
        token_type=chatbot,
    )


def revoke_turn_credential(token) -> None:
    """Withdraw it, whether or not the turn ended well."""
    from phoxtail.tokens.services import AccessTokenService

    AccessTokenService(token).admin.revoke()


# Both of the above are ordinary synchronous functions and the ``await``
# is added here, at the one place that needs it. Keeping the decision of
# *what a turn's credential looks like* out of the async plumbing is what
# lets it be read and tested directly, without a thread, an event loop or
# a database reachable from one.
_amint = sync_to_async(mint_turn_credential)
_arevoke = sync_to_async(revoke_turn_credential)


@contextlib.asynccontextmanager
async def acting_as(user):
    """Run a turn as *user*, with a credential of their own.

    Sets the credential in two places, because two different things ask
    for it and neither can see the other:

    - ``phoxtail.mcp._http`` asks what to send with an outbound API call;
    - the MCP tool registry asks what the caller may be offered, through
      the SDK's own auth context, which is what ``get_access_token()``
      reads when no HTTP request is in flight.

    Both are context variables, so two turns running at once each see
    their own and neither can be handed the other's.

    The token is revoked on the way out rather than left to expire. A turn
    that raises still revokes, because the credential outliving the
    exchange it was minted for is the only way a short life stops being
    short.
    """
    from mcp.server.auth.middleware.auth_context import (
        AuthenticatedUser,
        auth_context_var,
    )

    from phoxtail.mcp._http import use_token
    from phoxtail.mcp.authorization import as_access_token

    token, raw = await _amint(user)
    auth_reset = auth_context_var.set(AuthenticatedUser(as_access_token(raw, token)))
    try:
        with use_token(raw):
            yield token
    finally:
        auth_context_var.reset(auth_reset)
        await _arevoke(token)
