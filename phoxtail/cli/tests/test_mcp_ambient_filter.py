"""A local session is offered only what its stored credential covers.

fastmcp skips authorization on stdio, correctly: there is no caller to
authenticate when the server is a subprocess its client spawned. But the
process does hold a credential — the one every tool call is about to
spend — and its scopes are knowable before anything is offered.

What is asserted here is the shape of that filter, not the scope check
itself (``test_mcp_scoped.py`` owns that): which transports it acts on,
which tools survive it, and the three ways it declines to filter at all.
The fail-open cases are the ones worth pinning, because each of them is a
silent behaviour that would otherwise only be noticed as an empty
catalogue.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

from phoxtail.mcp.authorization import (
    AmbientCredentialFilter,
    AuthorityUnreachable,
    local_only,
    scoped,
)

PUBLISH = "wagtailcore.publish_page"
EDIT = "phoxtail_streams.change_blockvariant"


def _tool(name, auth=None):
    return SimpleNamespace(name=name, auth=auth, tags=set())


SESSION_TOOL = _tool("phoxtail_studio_open_variant", auth=[local_only])
PUBLISH_TOOL = _tool("phoxtail_pages_publish", auth=[scoped(PUBLISH)])
EDIT_TOOL = _tool("phoxtail_studio_push_variant", auth=[scoped(EDIT)])
VOCABULARY_TOOL = _tool("phoxtail_page_types_list", auth=None)

ALL_TOOLS = [SESSION_TOOL, PUBLISH_TOOL, EDIT_TOOL, VOCABULARY_TOOL]


def _token(*scopes, unrestricted=False):
    return SimpleNamespace(
        scopes=list(scopes),
        claims={"unrestricted": unrestricted, "is_superuser": False},
    )


async def _call_next(_context):
    return list(ALL_TOOLS)


def _offered(monkeypatch, *, over_http=False, raw="phxt_stored", verify=None):
    """Names the filter offers, with each of its three inputs stubbed.

    The transport oracle, the stored credential and the authority are the
    only things it reads, and every case below is a different answer to
    one of them.

    Driven through ``asyncio.run`` rather than as an async test: the hook
    is async because fastmcp's middleware protocol is, and the suite
    installs no async plugin. A bare ``async def test_`` would be
    collected, never awaited, and reported as passing.
    """
    monkeypatch.setattr("phoxtail.mcp.authorization.serving_over_http", lambda: over_http)
    monkeypatch.setattr("phoxtail.mcp.authorization.outbound_token", lambda: raw)
    if verify is not None:
        monkeypatch.setattr(
            "phoxtail.mcp.authorization.WhoamiVerifier.verify_token",
            verify,
        )
    tools = asyncio.run(AmbientCredentialFilter().on_list_tools(None, _call_next))
    return [t.name for t in tools]


def _answers(token):
    async def verify_token(self, raw):
        return token

    return verify_token


class TestWhatSurvivesTheFilter:
    def test_a_narrow_token_loses_the_tools_it_cannot_use(self, monkeypatch):
        offered = _offered(monkeypatch, verify=_answers(_token(PUBLISH)))
        assert PUBLISH_TOOL.name in offered
        assert EDIT_TOOL.name not in offered

    def test_the_session_tools_stay(self, monkeypatch):
        """The whole reason a local session is worth having.

        ``local_only`` is answered by the transport, and on stdio the
        answer is yes. A filter that read only scopes would drop the five
        tools that can *only* work here — so it runs the component's own
        checks, whatever they happen to ask.
        """
        offered = _offered(monkeypatch, verify=_answers(_token(PUBLISH)))
        assert SESSION_TOOL.name in offered

    def test_a_tool_declaring_nothing_is_offered(self, monkeypatch):
        """A vocabulary has no codename to name and asks for none."""
        offered = _offered(monkeypatch, verify=_answers(_token(PUBLISH)))
        assert VOCABULARY_TOOL.name in offered

    def test_an_unrestricted_token_keeps_everything(self, monkeypatch):
        offered = _offered(monkeypatch, verify=_answers(_token(unrestricted=True)))
        assert offered == [t.name for t in ALL_TOOLS]


class TestWhenItDeclinesToFilter:
    """Three ways of having no answer, and none of them empties the list.

    A catalogue that has quietly become empty is indistinguishable from a
    project that offers nothing, and an agent reports it as such. Every
    case here is a missing answer rather than a negative one, and the
    honest response to a missing answer is to advertise everything and let
    the API — which is the authority, and is checked regardless — refuse.
    """

    def test_over_http_it_does_nothing(self, monkeypatch):
        """The registry has already filtered against the caller's bearer.

        Filtering again against this process's ambient token would narrow
        a remote caller by a credential that is not theirs.
        """
        offered = _offered(monkeypatch, over_http=True, verify=_answers(_token(PUBLISH)))
        assert offered == [t.name for t in ALL_TOOLS]

    def test_no_stored_credential_offers_everything(self, monkeypatch):
        """A project nobody has run ``phoxtail auth login`` in."""
        offered = _offered(monkeypatch, raw=None)
        assert offered == [t.name for t in ALL_TOOLS]

    def test_an_unreachable_authority_offers_everything(self, monkeypatch):
        async def unreachable(self, raw):
            raise AuthorityUnreachable("down")

        offered = _offered(monkeypatch, verify=unreachable)
        assert offered == [t.name for t in ALL_TOOLS]

    def test_any_other_failure_offers_everything(self, monkeypatch):
        """Not only the failure this module has a name for.

        Reading the credentials file, resolving the project's api_url and
        building the request each raise in their own vocabulary, and this
        hook stands between an agent and the whole surface. A filter that
        raises leaves no tools at all — strictly worse than the unfiltered
        listing it replaced.
        """

        async def broken(self, raw):
            raise RuntimeError("something nobody anticipated")

        offered = _offered(monkeypatch, verify=broken)
        assert offered == [t.name for t in ALL_TOOLS]

    def test_an_unreadable_credential_offers_everything(self, monkeypatch):
        """The failure before the authority is ever asked."""

        def explode():
            raise OSError("credentials file is not readable")

        monkeypatch.setattr("phoxtail.mcp.authorization.serving_over_http", lambda: False)
        monkeypatch.setattr("phoxtail.mcp.authorization.outbound_token", explode)
        import asyncio

        tools = asyncio.run(AmbientCredentialFilter().on_list_tools(None, _call_next))
        assert [t.name for t in tools] == [t.name for t in ALL_TOOLS]

    def test_a_refused_credential_offers_everything(self, monkeypatch):
        """Expired or revoked: every call will fail at the API saying so."""
        offered = _offered(monkeypatch, verify=_answers(None))
        assert offered == [t.name for t in ALL_TOOLS]


class TestTheFixtureItself:
    def test_the_tools_do_not_all_declare_the_same_thing(self):
        """Guards every assertion above.

        Each case distinguishes tools by what they declare, so a fixture
        where they declared alike would let a filter that returns its
        input unchanged pass the whole file.
        """
        assert len({id(t.auth) for t in ALL_TOOLS}) == len(ALL_TOOLS)
