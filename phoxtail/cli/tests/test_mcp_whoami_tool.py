"""The tool that explains what a filtered catalogue left out.

Filtering removed the one thing that told an agent a capability exists
and is out of reach — an API refusal naming the permission. These assert
the two halves that give it back: the ceiling is reported, and what the
last listing withheld is reported alongside it, with the codenames that
would have been enough.

The tool is local-only, and that is asserted here rather than left to
review: over HTTP the list of withheld tools is a map of the surface, and
nothing about the tool's shape makes that obvious.
"""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

from phoxtail.mcp.authorization import AmbientCredentialFilter, local_only, scoped

PUBLISH = "wagtailcore.publish_page"
EDIT = "phoxtail_streams.change_blockvariant"


def _import_tool():
    """Imported inside the tests, because importing registers it.

    ``phoxtail.mcp.credential`` registers on the shared server by import
    side effect, and ``on_duplicate="error"`` means a second import at
    collection time would be a hard failure rather than a no-op.
    """
    from phoxtail.mcp.credential import phoxtail_whoami

    return phoxtail_whoami


def _registered_tool():
    """The tool as the server holds it, which is where ``auth`` lives.

    The decorator leaves the plain function bound to the module name, so
    the annotation has to be read off the registry rather than off the
    import.
    """
    from phoxtail.mcp import mcp_server

    _import_tool()
    return asyncio.run(mcp_server.get_tool("phoxtail_whoami"))


def _token(*scopes, unrestricted=False):
    return SimpleNamespace(
        scopes=list(scopes),
        claims={"unrestricted": unrestricted, "is_superuser": False},
    )


def _tool(name, auth):
    return SimpleNamespace(name=name, auth=auth, tags=set())


def _run_filter(monkeypatch, tools, token):
    async def call_next(_context):
        return list(tools)

    async def verify_token(self, raw):
        return token

    monkeypatch.setattr("phoxtail.mcp.authorization.serving_over_http", lambda: False)
    monkeypatch.setattr("phoxtail.mcp.authorization.outbound_token", lambda: "phxt_x")
    monkeypatch.setattr("phoxtail.mcp.authorization.WhoamiVerifier.verify_token", verify_token)
    asyncio.run(AmbientCredentialFilter().on_list_tools(None, call_next))


def _answer(monkeypatch, status=200, body=None):
    body = body if body is not None else {"email": "a@b.test", "scopes": [PUBLISH]}
    monkeypatch.setattr(
        "phoxtail.mcp.credential.request",
        lambda *a, **k: SimpleNamespace(status_code=status, json=lambda: body, text=json.dumps(body)),
    )


def _call(monkeypatch, **kwargs):
    tool = _import_tool()
    _answer(monkeypatch, **kwargs)
    return json.loads(tool())


class TestWhatItReports:
    def test_it_names_the_withheld_tool_and_what_it_needed(self, monkeypatch):
        _run_filter(
            monkeypatch,
            [
                _tool("phoxtail_pages_publish", [scoped(PUBLISH)]),
                _tool("phoxtail_studio_push_variant", [scoped(EDIT)]),
            ],
            _token(PUBLISH),
        )
        answer = _call(monkeypatch)
        assert answer["withheld_tools"] == {"phoxtail_studio_push_variant": [EDIT]}
        assert answer["withheld_tool_count"] == 1
        assert answer["withheld_tools_known"] is True

    def test_it_reports_the_credentials_own_ceiling(self, monkeypatch):
        _run_filter(monkeypatch, [], _token(PUBLISH))
        answer = _call(monkeypatch)
        assert answer["scopes"] == [PUBLISH]
        assert answer["email"] == "a@b.test"

    def test_a_tool_with_an_opaque_check_names_no_scope(self, monkeypatch):
        """A list holding one opaque check discloses none of its scopes.

        ``local_only`` cannot say what is missing, because no scope would
        fix it — and fastmcp withholds the *whole* shortfall rather than
        the failing check's share, so that a denial for one reason never
        advertises the scopes of another.

        The consequence is worth stating: a tool carrying ``local_only``
        beside a scope can never explain itself here, whichever of the two
        refused it. It does not bite today because ``local_only`` passes on
        a local session and the filter runs nowhere else — so a tool that
        has one is never withheld for the other.
        """
        _run_filter(
            monkeypatch,
            [_tool("phoxtail_studio_open_variant", [local_only, scoped(EDIT)])],
            _token(PUBLISH),
        )
        answer = _call(monkeypatch)
        assert answer["withheld_tools"] == {"phoxtail_studio_open_variant": []}

    def test_nothing_withheld_from_an_unrestricted_key(self, monkeypatch):
        _run_filter(
            monkeypatch,
            [_tool("phoxtail_pages_publish", [scoped(PUBLISH)])],
            _token(unrestricted=True),
        )
        answer = _call(monkeypatch)
        assert answer["withheld_tools"] == {}

    def test_a_failing_api_is_reported_rather_than_guessed(self, monkeypatch):
        _run_filter(monkeypatch, [], _token(PUBLISH))
        answer = _call(monkeypatch, status=503, body={"detail": "down"})
        assert answer["error"] == "whoami_failed"
        assert answer["status"] == 503


class TestWhereTheAnswerComesFrom:
    """It asks the API only when nothing has already answered.

    Inside a chat turn this runs in the web container, so asking the API
    would be Django making an HTTP request to itself and holding a worker
    until it replies — which with one worker never happens. The credential
    is in context by then, so the question has an answer without the call.
    """

    def test_a_resolved_credential_is_read_rather_than_re_asked(self, monkeypatch):
        from fastmcp.server.auth import AccessToken

        asked = []
        monkeypatch.setattr(
            "phoxtail.mcp.credential.request",
            lambda *a, **k: asked.append(1) or SimpleNamespace(status_code=500, text=""),
        )
        monkeypatch.setattr(
            "fastmcp.server.dependencies.get_access_token",
            lambda: AccessToken(
                token="t",
                client_id="alice@example.invalid",
                subject="uuid-1",
                scopes=[PUBLISH],
                expires_at=None,
                claims={"unrestricted": False, "is_superuser": False},
            ),
        )
        answer = json.loads(_import_tool()())
        assert asked == [], "asking the API from inside the turn can deadlock a worker"
        assert answer["email"] == "alice@example.invalid"
        assert answer["scopes"] == [PUBLISH]

    def test_it_falls_back_to_the_api_when_nothing_is_resolved(self, monkeypatch):
        """A local stdio session, where the registry resolves no credential."""
        monkeypatch.setattr("fastmcp.server.dependencies.get_access_token", lambda: None)
        answer = _call(monkeypatch)
        assert answer["email"] == "a@b.test"


class TestWhatItDeclinesToClaim:
    def test_it_says_so_when_it_did_not_do_the_withholding(self, monkeypatch):
        """A chat turn is narrowed by the registry, not by our filter.

        The registry does not report what it left out, so this server does
        not know. An empty mapping would read as "nothing was withheld",
        which is the one wrong answer available.
        """
        from phoxtail.mcp.authorization import _Withheld

        monkeypatch.setattr("phoxtail.mcp.credential._withheld", _Withheld())
        answer = _call(monkeypatch)
        assert answer["withheld_tools_known"] is False
        assert "withheld_tools" not in answer

    def test_a_measured_empty_catalogue_is_not_the_same_answer(self, monkeypatch):
        """Nothing withheld, and known to be nothing, still reports a map."""
        _run_filter(monkeypatch, [], _token(PUBLISH))
        answer = _call(monkeypatch)
        assert answer["withheld_tools_known"] is True
        assert answer["withheld_tools"] == {}


class TestItIsLocalOnly:
    def test_the_tool_declares_local_only(self):
        """Over HTTP the withheld list is a map of the surface.

        Nothing about the tool's shape makes that obvious, so the check is
        asserted rather than trusted to review.
        """
        assert local_only in _registered_tool().auth
