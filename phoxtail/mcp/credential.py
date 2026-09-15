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

**It answers for the credential, which is not always the person.** On a
local session the two are the same: the process runs as whoever started
it and spends their stored token. The in-process chatbot is neither over
HTTP nor a separate credential — it calls the API with this container's
ambient token — so asked there, this reports the token's owner rather
than the person in the conversation. That is the same gap every tool on
that path has, not one this introduces, and it closes when a chat turn
carries a credential of its own. Until then the answer is true about the
credential and can be wrong about the person, which for a tool called
whoami is worth knowing before trusting it.

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
def phoxtail_whoami() -> str:
    """Who this session is, and what its credential does not cover."""
    response = request("GET", "/api/whoami/")
    if response.status_code >= 400:
        return json.dumps(
            {
                "error": "whoami_failed",
                "status": response.status_code,
                "detail": response.text[:500],
            }
        )

    identity = response.json()
    withheld = _withheld.entries()
    return json.dumps(
        {
            **identity,
            # Named separately from `scopes` because they are different
            # kinds of fact: one is what the key carries, the other is what
            # this catalogue lost by carrying only that. An empty mapping
            # means nothing was withheld, which for an unrestricted key is
            # the normal answer.
            "withheld_tools": withheld,
            "withheld_tool_count": len(withheld),
        }
    )
