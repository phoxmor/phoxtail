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

import logging
from datetime import datetime

import httpx
from fastmcp.exceptions import AuthorizationError, FastMCPError
from fastmcp.server.auth import AccessToken, AuthContext, TokenVerifier
from fastmcp.server.middleware import Middleware
from fastmcp.utilities.authorization import (
    _RequireScopes,
    run_auth_checks,
    scope_requirements,
)

from phoxtail.mcp._http import outbound_token, serving_over_http, url

logger = logging.getLogger(__name__)

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
                    "bundles": list(data.get("bundles", [])),
                },
            )
        except (ValueError, KeyError, TypeError) as exc:
            raise AuthorityUnreachable(
                f"This project's API gave an answer this server could not read when asked to identify the caller: {exc}"
            ) from exc


def as_access_token(raw_token: str, token) -> AccessToken:
    """A stored ``AccessToken`` row, in the shape the tool registry reads.

    The registry never sees phoxtail's model. It asks the MCP SDK for "the
    credential of the caller being served" and gets fastmcp's `AccessToken`
    — which is what :class:`WhoamiVerifier` builds over HTTP, by asking the
    API. In-process there is nobody to ask: the row is right here, minted a
    moment ago by this process, so the same shape is filled in directly.

    Asking ``/whoami/`` for a token we just wrote would be a round trip to
    be told what we already know, and would make every chat turn depend on
    the project's own API being reachable from inside itself.

    The two must stay in step, and the fields are the reason they can: both
    carry the owner's address, their uuid, the scopes as codenames — the
    stored names expanded, exactly as ``/whoami/`` reports them — the
    expiry, and ``unrestricted`` as a claim rather than an expanded list of
    codenames.
    """
    from phoxtail.tokens.bundles import expand, is_bundle

    return AccessToken(
        token=raw_token,
        client_id=token.user.email,
        subject=str(token.user.uuid),
        scopes=sorted(expand(token.scopes)),
        expires_at=int(token.expires_at.timestamp()) if token.expires_at else None,
        claims={
            "unrestricted": bool(token.unrestricted),
            "is_superuser": bool(token.user.is_superuser),
            "bundles": [name for name in token.scopes if is_bundle(name)],
        },
    )


class _Withheld:
    """What the last filtered listing left out, and what it would have taken.

    The catalogue is where an agent learns a tool exists, so a filtered
    one silently removes the only way to find out that a capability is
    there and out of reach. This is what gives that back: the filter
    writes down what it dropped, and ``phoxtail_whoami`` reads it, so an
    agent can say *which permission* is missing rather than reporting the
    tool as nonexistent.

    Process-wide mutable state, which is safe for exactly one reason: the
    filter only ever runs on stdio, where the process serves a single
    local session. Over HTTP it returns before reaching here, so two
    callers can never write over each other — and the tool that reads it
    is itself ``local_only``, so this never answers a stranger.
    """

    def __init__(self) -> None:
        # ``None`` until a listing has actually been filtered here, and it
        # is not the same statement as ``{}``. The filter stands down when
        # somebody else supplied the credential — a chat turn, whose
        # catalogue the registry narrows instead — and in that case what
        # was dropped is known to the registry and not to us. Reporting an
        # empty mapping there would claim nothing was withheld, which is
        # the opposite of true.
        self._entries: dict[str, list[str]] | None = None

    def replace(self, entries: dict[str, list[str]]) -> None:
        self._entries = entries

    def entries(self) -> dict[str, list[str]] | None:
        return None if self._entries is None else dict(self._entries)


_withheld = _Withheld()


class AmbientCredentialFilter(Middleware):
    """Offer a local session only the tools its stored credential covers.

    **Why this exists at all.** fastmcp skips authorization entirely on
    stdio, and says why: "STDIO has no auth concept". That is true about
    *authentication* and it is the right default. A stdio server is a
    subprocess its client spawned, so there is no connection to verify and
    no credential in the protocol — identity is settled by the operating
    system before a byte moves.

    It is not true about the *ceiling*. Phoxtail has an ambient credential
    that :func:`phoxtail.mcp._http.outbound_token` is going to present on
    every call this process makes, and its scopes are knowable before any
    tool is offered. Nobody is being authenticated here; a limit that the
    caller has already accepted is being applied to what they are shown.

    So the asymmetry this removes is not a security one. Over HTTP the
    ceiling is imposed by whoever presented the token; over stdio it is
    self-imposed by the process. What both have in common is the thing
    filtering is for: a catalogue the size of the whole surface is a
    permanent tax on every request, and a model choosing among the tools
    that can work chooses better than one choosing among all of them.

    **The listing is filtered and that is the whole of it.** The server
    would still serve a call for a withheld tool — the registry skips auth
    on stdio and this hook only filters the listing — but no MCP client
    sends a call for a name it was not offered, so that path has no caller
    and is not a fallback.

    What that costs is the refusal. An API 403 names the permission that
    would have allowed the act, which is the one thing an agent can act
    on; a tool that is simply absent says nothing. Enforcement is at the
    API and stays there, but the explanation leaves with the catalogue
    entry, and the place to put it back is a tool reporting what the
    credential covers.

    **It fails open, deliberately, and only here.** With no stored
    credential — a project nobody has run ``phoxtail auth login`` in — or
    with the API unreachable, every tool is offered. That is the exact
    opposite of :class:`AuthorityUnreachable`, which refuses to let an
    outage be read as "permitted nothing", and the two are not in conflict:
    that answer stands between a caller and an act, this one only decides
    what is advertised. That is the opposite
    of :class:`AuthorityUnreachable`, which refuses to let an outage be
    read as "permitted nothing", and the difference is the stake: that
    answer stands between a caller and an act, this one only decides what
    is advertised. An outage that emptied the catalogue would look exactly
    like a project that offers nothing.
    """

    async def on_list_tools(self, context, call_next):
        tools = await call_next(context)

        # Somebody has already supplied a credential for this call — a
        # chat turn acting as its person. The registry has filtered
        # against that one, which is the right one; narrowing again by
        # this machine's stored key would answer as a different person
        # entirely, and a stricter one by coincidence rather than design.
        from fastmcp.server.dependencies import get_access_token

        if get_access_token() is not None:
            return tools

        # The early return is load-bearing, not an optimisation. Over HTTP
        # the registry has already filtered the catalogue against the
        # caller's own bearer, including `local_only`; filtering again here
        # would narrow — or widen — a remote caller by this process's
        # ambient credential, which is not theirs. This hook exists only
        # because the registry skips that work on stdio.
        #
        # Not fastmcp's transport name, though `Context.transport` would
        # report it: the question here is whether a caller's own bearer is
        # in flight to defer to, which is what this answers directly. The
        # two coincide today and would part the moment a transport carried
        # no credential.
        if serving_over_http():
            return tools

        # Every way of failing to learn the ceiling is caught, not only
        # `AuthorityUnreachable`: reading the credentials file, resolving
        # the project's api_url and building the request all raise in their
        # own vocabularies, and this hook stands between an agent and the
        # entire tool surface. An advisory filter that raises removes every
        # tool, which is the one outcome worth ruling out absolutely —
        # worse than the unfiltered listing it replaced, and reported by
        # the agent as a project that offers nothing.
        try:
            raw_token = outbound_token()
            token = await WhoamiVerifier().verify_token(raw_token) if raw_token else None
        except Exception:
            logger.warning(
                "Could not ask this project's API what the stored credential covers; offering the whole tool surface.",
                exc_info=True,
            )
            return tools

        # No credential stored, or one the API refused as expired or
        # revoked. Neither is an answer about scopes, and both are already
        # about to be reported by the API in its own words on the first
        # call — which says more than a catalogue that has quietly shrunk.
        if token is None:
            return tools

        offered = []
        withheld: dict[str, list[str]] = {}
        for tool in tools:
            if tool.auth is None:
                offered.append(tool)
                continue
            # The component's own checks, not only its scopes: `local_only`
            # is one of them and answers True here, which is what keeps the
            # session tools — the whole reason a local session is worth
            # having — in a filtered listing.
            ctx = AuthContext(token=token, component=tool)
            try:
                if await run_auth_checks(tool.auth, ctx):
                    offered.append(tool)
                    continue
            except AuthorizationError:
                pass
            # What it would have taken, recorded rather than recomputed
            # later: this is the set the agent's catalogue is actually
            # missing, and a second derivation could disagree with it.
            # `scope_requirements` answers None when any check is opaque —
            # a denial no scope would fix — and an empty list reads the
            # same way, so both become "withheld, reason unnamed".
            withheld[tool.name] = scope_requirements(tool.auth, ctx) or []
        _withheld.replace(withheld)
        return offered
