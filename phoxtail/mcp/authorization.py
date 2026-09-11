"""Who is calling, and what they may be offered.

Two things live here because they are two halves of one question. A
:class:`WhoamiVerifier` turns the opaque bearer at the door into a caller
with a name and a ceiling, by asking the only thing that knows. The checks
below are then handed that caller, alongside the component being reached,
and answer whether the one may have the other.

fastmcp asks each component one question — its ``auth`` checks — and asks
it at both moments that matter: when the catalogue is listed, where a
failing check drops the component, and when it is addressed by name, where
the same check makes it indistinguishable from one that does not exist.
Both are enforced by the registry itself (``list_tools``, ``get_tool``,
``get_resource``, ``get_prompt``), so there is no serving path that can
skip them and no middleware anyone has to remember to install.

A check is any ``Callable[[AuthContext], bool]``. The context carries the
caller's token and the component being reached, which is enough to answer
questions that have nothing in common with each other: one tool is limited
by what a credential permits, another by the transport it arrived on, and
neither has to know the other exists. That is why the checks live here as
plain functions rather than behind a vocabulary of our own — naming the
check on the tool says the same thing with nothing in between.

**Neither moment is the last line of defence, and neither pretends to be.**
A shorter catalogue is economy and honesty, not a lock: anything reaching
the API is checked there again, by the authority, with no memory of what
was decided here.
"""

from __future__ import annotations

from datetime import datetime

import httpx
from fastmcp.exceptions import FastMCPError
from fastmcp.server.auth import AccessToken, AuthContext, TokenVerifier
from fastmcp.utilities.authorization import _RequireScopes

from phoxtail.mcp._http import serving_over_http, url

# Deliberately not the tool-call timeout. A tool may legitimately work for
# half a minute; asking who someone is may not. This runs on every inbound
# request and a client sends several per session, so a hung API waiting on
# the tool timeout would hold each of them in turn — minutes of silence to
# learn that something is down. Failing fast is what makes the outage
# message arrive while anyone is still watching for it.
INTROSPECTION_TIMEOUT = 5.0


def local_only(context: AuthContext) -> bool:
    """Offer this component only to a caller sharing a machine with us.

    The sessions tools write files to this server's own disk and return
    their paths, so an agent can read and edit them in place. Reached over
    HTTP the agent is somewhere else entirely and those paths name nothing
    it can open — and the tool does not fail saying so, it succeeds and
    hands back directions to a building in another city. That is what this
    guards: not a permission, but a capability that does not survive the
    distance.

    Nothing about identity enters it. A superuser on a phone is exactly as
    far away as anyone else, so the question is answered by the transport
    and by nothing else.

    Note what it does *not* cover. A tool that takes a path as an argument,
    like uploading a staged file, asks a question about the argument rather
    than about the caller. No check standing outside the tool can answer
    that, and it belongs inside, where the path is known.
    """
    return not serving_over_http()


class _Scoped(_RequireScopes):
    """All of these codenames, or a credential that names no ceiling at all.

    fastmcp's own ``require_scopes`` reads the scope list and nothing else,
    which is the whole answer for OAuth, where a token without a scope was
    not granted it. A phoxtail token has a second shape: ``unrestricted``
    is a flag, and such a token carries an *empty* scope list — not because
    it is permitted nothing but because there is no ceiling to write down.
    Expanding it into every codename in the project is what this project
    removed deliberately; it would freeze at issue time and keep granting
    capabilities installed afterwards. So the flag stays a flag, and the
    bypass lives here.

    Subclassing rather than writing a plain callable is what keeps the
    check *scope-aware*. fastmcp tests that with ``isinstance``, and a
    check that fails it is opaque: it denies without saying what is
    missing, and — because one opaque check withholds the whole list — it
    silences its siblings too. Opaque is the right answer for
    :func:`local_only`, whose denial no scope would fix. It is the wrong
    answer here, where the shortfall is exactly the thing a caller can act
    on.
    """

    def __call__(self, ctx: AuthContext) -> bool:
        if ctx.token is not None and ctx.token.claims.get("unrestricted"):
            return True
        return super().__call__(ctx)

    def missing_scopes(self, ctx: AuthContext) -> set[str]:
        """Nothing is missing from a credential that has no ceiling.

        The inherited comparison is ``required - token.scopes``, and an
        unrestricted token's scopes are empty — so left alone it would
        report every codename as missing for a caller it had just
        admitted. ``run_auth_checks_with_shortfall`` would mask that,
        since it only unions shortfalls once something has failed, but
        ``scope_requirements`` computes from the token and component
        without running any check. That is the path that would read a
        phantom shortfall off the one credential that has none.
        """
        if ctx.token is not None and ctx.token.claims.get("unrestricted"):
            return set()
        return super().missing_scopes(ctx)


def scoped(*codenames: str) -> _Scoped:
    """Offer this component to a credential permitting acts of this kind.

    Used as ``auth=[scoped("wagtailcore.publish_page")]``. Deliberately
    the same name as :func:`phoxtail.api.auth.scoped`, at the same level
    — the thing that goes in ``auth=`` — because it is the same idea, and
    the two must name the same codename for a given act or the catalogue
    and the doors that open will disagree.

    Returns the concrete check rather than ``AuthCheck``, which is only
    ``Callable[[AuthContext], bool]``: reading ``missing_scopes`` off the
    result is the point, and the annotation should say so.

    Only the credential's half of the question, and the coarser half. The
    endpoint this component reaches asks it again, alongside whether the
    *person* may act, which is answered where the act happens and is often
    finer than a codename can express.
    """
    return _Scoped(codenames)


def _epoch(expires_at: str | None) -> int | None:
    """The expiry as fastmcp states it: whole seconds, or nothing.

    ``/whoami/`` reports an ISO timestamp, and ``None`` for a browser
    session, which has no credential to expire. Translating here rather
    than changing the endpoint keeps the API's answer in the shape its own
    callers read.
    """
    if not expires_at:
        return None
    return int(datetime.fromisoformat(expires_at).timestamp())


class AuthorityUnreachable(FastMCPError):
    """The authority could not be asked at all.

    About us, not the caller. Raised rather than returned, precisely so
    it does *not* become a ``401``: nothing the caller does with their
    credential will help, and sending them to re-authenticate during an
    outage is how a broken database gets diagnosed as an expired token.

    An unanswered question is reported as unanswered. It is never
    resolved into "permitted nothing", which an agent reads as a project
    that genuinely offers nothing and reports as such.
    """


class WhoamiVerifier(TokenVerifier):
    """Ask the authority who a bearer belongs to, once per request.

    The MCP server holds no database and validates nothing. A bearer
    arriving over HTTP is an opaque string to it — it cannot be read,
    only forwarded. That is deliberate (the API is the sole authority),
    and it leaves this layer blind at exactly the moment it needs to see:
    to offer a caller only the tools their credential covers, it must
    first know what that credential is.

    So it asks. ``GET /api/whoami/`` is the authority answering "this
    credential — whose is it, and what may it be used for". Asking the
    authority does not make this layer an authority; manufacturing the
    answer would.

    **Nothing here decides anything.** The answer is used to show and to
    refuse early; the act itself still travels to the API, which re-checks
    with no cache and no memory of what was said here. That ordering is
    what makes resolving identity ahead of the act safe, and it must not
    be reversed: the moment this answer becomes the only thing between a
    caller and an effect, its age starts to matter.

    **No cache, and no TTL to choose.** fastmcp calls this once per
    inbound request, which is the cheapest correct choice and the only one
    with no staleness at all — a listing and a call are separate requests
    and each asks afresh. The library ships a ``TokenCache``; adopting it
    is a trade to make against measurements, not in advance.
    """

    async def verify_token(self, token: str) -> AccessToken | None:
        try:
            async with httpx.AsyncClient(timeout=INTROSPECTION_TIMEOUT) as client:
                response = await client.get(
                    url("/api/whoami/"),
                    headers={"Authorization": f"Bearer {token}"},
                )
        except httpx.HTTPError as exc:
            raise AuthorityUnreachable(f"Could not reach this project's API: {exc}") from exc

        if response.status_code in (401, 403):
            # A refused credential is reported by returning nothing, which
            # fastmcp turns into a 401 carrying the WWW-Authenticate
            # challenge a client needs in order to go and obtain a better
            # one. Raising here would produce a 500 instead, telling the
            # caller their key is fine and we are broken.
            return None
        if response.status_code >= 400:
            raise AuthorityUnreachable(
                f"This project's API answered {response.status_code} when asked to identify the caller."
            )

        try:
            data = response.json()
            return AccessToken(
                token=token,
                # The address the caller signs in with, which is what
                # reads in an audit line. The uuid is the name every API
                # path and tool argument uses, so it is the identifier to
                # hand back, and goes in `subject`.
                client_id=data["email"],
                subject=str(data["user_uuid"]),
                scopes=list(data["scopes"]),
                expires_at=_epoch(data.get("expires_at")),
                # `unrestricted` cannot be expressed as scopes, and must
                # not be. Filling the list with every codename in the
                # project would keep granting capabilities installed after
                # the token was issued — the wildcard this project removed
                # deliberately, rebuilt once per request. It stays a flag.
                claims={
                    "unrestricted": bool(data["unrestricted"]),
                    "is_superuser": bool(data["is_superuser"]),
                },
            )
        except (ValueError, KeyError, TypeError) as exc:
            raise AuthorityUnreachable(
                f"This project's API gave an answer this server could not read when asked to identify the caller: {exc}"
            ) from exc
