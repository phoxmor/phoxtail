"""The tool that explains a local session's own credential.

A filtered catalogue is cheaper to reason over and costs one thing: a
tool that is out of a credential's reach is now absent rather than
refused, and an absent tool names no permission. The agent stops saying
"you need wagtailcore.view_page" and starts saying "no such tool", which
is true and useless.

This gives that back. It reports the ceiling of the credential this
process is spending, and what the last listing withheld from it — so the
answer to "why can you not list pages" is a permission the user can go
and grant, rather than a capability that appears not to exist.

**It answers for the credential, and the credential is the person.** On a
local session the process runs as whoever started it and spends their
stored token. In a chat turn the person has a credential minted for them,
so this reports them. Both are the same rule — *whoever this call will go
out as* — which is the answer a caller can act on, since it is also the
answer every door will give.

**``withheld_tools`` is only reported where this server did the
withholding.** The local filter records what it dropped; a chat turn is
narrowed by the tool registry instead, which does not say what it left
out. Asked there, the key is absent rather than empty — an empty mapping
would claim nothing was withheld, which is the opposite of what is known.

**Local sessions only.** Over HTTP a shorter catalogue also declines to
confirm what exists, and naming what was withheld would hand a stranger
a map of the surface. On stdio the caller owns the process and could
read this file, so there is nothing to withhold and only a diagnostic to
gain. It is also the only transport that needs it: a remote caller is
refused with an RFC 6750 ``insufficient_scope`` challenge that names the
shortfall in the protocol itself.
"""

from __future__ import annotations

import json

from phoxtail.mcp import mcp_server
from phoxtail.mcp._http import request
from phoxtail.mcp.authorization import _withheld, local_only


@mcp_server.tool(
    # No scope of its own, and deliberately not an oversight. A credential
    # cannot be asked to permit the act of reading what it permits — that
    # is the one question whose answer must not sit behind its own answer.
    # Note this is the opposite default from the API, where an endpoint
    # declaring nothing refuses a scoped token and has to say
    # `authenticated()` to mean this.
    auth=[local_only],
    name="phoxtail_whoami",
    description=(
        "Report who this session is acting as, what its credential permits, "
        "and which tools were withheld from the tool list because of it. "
        "Call this when a tool the user asked for does not appear to exist, "
        "or when a call is refused for a permission: the answer names the "
        "exact permission to grant. The tool list is filtered by the stored "
        "token's scopes, so a missing tool usually means a narrow key rather "
        "than a missing capability."
    ),
)
def _identity() -> dict:
    """What this call's credential is, from whoever already knows.

    Two sources, and the order avoids asking a question that has already
    been answered:

    1. **The credential resolved for this call.** Over HTTP the verifier
       has just asked the API; in a chat turn the token was minted here a
       moment ago. Either way the answer is in hand, and re-asking would
       be a round trip to be told what this process already holds.
    2. **Nothing resolved** — a local session over stdio, where the
       registry skips authorization and the credential is only a string
       on disk. Then the API is the one thing that can read it.

    The first branch is not an optimisation. Inside a chat turn this code
    runs in the web container, so asking the API would be Django making an
    HTTP request to itself and holding a worker until it answers. With a
    single worker that does not return.
    """
    from fastmcp.server.dependencies import get_access_token

    token = get_access_token()
    if token is not None:
        return {
            "email": token.client_id,
            "user_uuid": token.subject,
            "is_superuser": bool(token.claims.get("is_superuser")),
            "unrestricted": bool(token.claims.get("unrestricted")),
            "scopes": list(token.scopes),
            "expires_at": token.expires_at,
        }

    response = request("GET", "/api/whoami/")
    if response.status_code >= 400:
        raise _Unanswerable(response.status_code, response.text[:500])
    return response.json()


class _Unanswerable(Exception):
    """The API refused or failed to say who the caller is."""

    def __init__(self, status: int, detail: str) -> None:
        self.status = status
        self.detail = detail


def phoxtail_whoami() -> str:
    """Who this session is, and what its credential does not cover."""
    try:
        identity = _identity()
    except _Unanswerable as exc:
        return json.dumps({"error": "whoami_failed", "status": exc.status, "detail": exc.detail})
    withheld = _withheld.entries()
    if withheld is None:
        # Nothing was measured here, so nothing is claimed. Saying so
        # beats an empty mapping, which an agent reads as "everything you
        # can see is everything there is".
        return json.dumps({**identity, "withheld_tools_known": False})

    return json.dumps(
        {
            **identity,
            "withheld_tools_known": True,
            # Named separately from `scopes` because they are different
            # kinds of fact: one is what the key carries, the other is what
            # this catalogue lost by carrying only that. An empty mapping
            # means nothing was withheld, which for an unrestricted key is
            # the normal answer.
            "withheld_tools": withheld,
            "withheld_tool_count": len(withheld),
        }
    )
