"""The MCP server asks the authority who a bearer belongs to.

The server holds no database and reads no token. What it knows about a
caller, it knows because it asked ``GET /api/whoami/`` and was told. These
tests are about the asking: what is carried across, and — the part worth
the most care — how each way of failing is reported, since the two ways
mean opposite things to whoever is waiting.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import httpx
import pytest
from pytest_httpx import HTTPXMock

from phoxtail.mcp._http import url
from phoxtail.mcp.authorization import AuthorityUnreachable, WhoamiVerifier

WHOAMI = url("/api/whoami/")


def _ask(token: str = "phxt_abc"):
    return asyncio.run(WhoamiVerifier().verify_token(token))


def _answer(**overrides):
    body = {
        "email": "caller@example.com",
        "user_uuid": "6f1d4e6c-6b1a-4a3b-9c4e-2f0a8d5e1b77",
        "is_superuser": True,
        "unrestricted": False,
        "scopes": ["wagtailcore.publish_page"],
        "expires_at": None,
    }
    body.update(overrides)
    return body


class TestWhatIsCarriedAcross:
    def test_the_bearer_is_forwarded_unread(self, httpx_mock: HTTPXMock):
        """The server cannot read a token. It can only hand it on."""
        httpx_mock.add_response(url=WHOAMI, json=_answer())
        _ask("phxt_secret")
        assert httpx_mock.get_requests()[0].headers["Authorization"] == "Bearer phxt_secret"

    def test_the_caller_is_named_twice_for_two_purposes(self, httpx_mock: HTTPXMock):
        """An address reads in an audit line; a uuid is an argument."""
        httpx_mock.add_response(url=WHOAMI, json=_answer())
        caller = _ask()
        assert caller.client_id == "caller@example.com"
        assert caller.subject == "6f1d4e6c-6b1a-4a3b-9c4e-2f0a8d5e1b77"

    def test_the_ceiling_is_carried_as_the_authority_stated_it(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(url=WHOAMI, json=_answer())
        caller = _ask()
        assert caller.scopes == ["wagtailcore.publish_page"]
        assert caller.claims["unrestricted"] is False

    def test_an_unrestricted_token_is_not_expanded_into_scopes(self, httpx_mock: HTTPXMock):
        """The flag stays a flag.

        Filling the list with every codename in the project would keep
        granting capabilities installed after the token was issued, which
        is the wildcard this project removed deliberately.
        """
        httpx_mock.add_response(url=WHOAMI, json=_answer(unrestricted=True, scopes=[]))
        caller = _ask()
        assert caller.claims["unrestricted"] is True
        assert caller.scopes == []

    def test_an_expiry_is_translated_into_the_shape_fastmcp_reads(self, httpx_mock: HTTPXMock):
        moment = datetime(2027, 3, 1, 12, 0, tzinfo=UTC)
        httpx_mock.add_response(url=WHOAMI, json=_answer(expires_at=moment.isoformat()))
        assert _ask().expires_at == int(moment.timestamp())

    def test_a_session_has_no_expiry_to_carry(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(url=WHOAMI, json=_answer(expires_at=None))
        assert _ask().expires_at is None


class TestTheTwoWaysOfFailing:
    """Collapsing these sends people hunting for a key problem in an outage."""

    @pytest.mark.parametrize("status", [401, 403])
    def test_a_refused_credential_is_reported_by_answering_nothing(self, httpx_mock: HTTPXMock, status):
        """Which fastmcp turns into a 401 the caller can act on."""
        httpx_mock.add_response(url=WHOAMI, status_code=status, json={"detail": "no"})
        assert _ask() is None

    def test_an_unreachable_authority_raises_rather_than_answering_nothing(self, httpx_mock: HTTPXMock):
        """Never a 401: no credential the caller holds would help."""
        httpx_mock.add_exception(httpx.ConnectError("refused"), url=WHOAMI)
        with pytest.raises(AuthorityUnreachable):
            _ask()

    def test_a_broken_authority_raises(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(url=WHOAMI, status_code=500, text="boom")
        with pytest.raises(AuthorityUnreachable):
            _ask()

    def test_an_unreadable_answer_raises(self, httpx_mock: HTTPXMock):
        """An answer we cannot parse is our problem, not the caller's."""
        httpx_mock.add_response(url=WHOAMI, json={"email": "caller@example.com"})
        with pytest.raises(AuthorityUnreachable):
            _ask()


class TestTheServerIsNotTheAuthority:
    def test_the_answer_is_asked_for_every_time(self, httpx_mock: HTTPXMock):
        """No cache, so nothing is ever remembered past the moment it was true."""
        httpx_mock.add_response(url=WHOAMI, json=_answer(), is_reusable=True)
        _ask()
        _ask()
        assert len(httpx_mock.get_requests()) == 2


class TestTheServerDeclaresIt:
    def test_the_server_names_an_authority(self):
        """Declared on the server itself, so no serving path can omit it.

        This is also what makes fastmcp wrap the HTTP route in a challenge:
        a request arriving with no credential is answered ``401`` with a
        ``WWW-Authenticate`` header, which is how a remote client learns
        where to go and authenticate. Removing this would silently take
        that away.
        """
        from phoxtail.mcp import mcp_server

        assert isinstance(mcp_server.auth, WhoamiVerifier)
