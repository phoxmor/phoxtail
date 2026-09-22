"""The API-wide default admits no one.

The default only ever answers for an endpoint that declares no ``auth=``,
and it asks nothing of the person. It used to admit a session and an
unrestricted token, so a forgotten endpoint was open to any logged-in user
whatever their permissions, unless its body checked for itself. Now
forgetting costs access, for every kind of caller, and never safety.

Driven through ninja rather than by calling the doors in a loop, so what is
tested is how ninja actually dispatches the default, not a copy of it.
"""

from __future__ import annotations

import pytest
from ninja import NinjaAPI, Router
from ninja.testing import TestClient

from phoxtail.api import api
from phoxtail.api.auth import PhoxtailSessionAuth
from phoxtail.tokens.tests.factories import AccessTokenFactory, UserFactory

pytestmark = pytest.mark.django_db


def _client():
    """One endpoint on the real default, and one under a router of its own."""
    probe = NinjaAPI(urls_namespace="test_default", auth=api.auth)

    @probe.get("/forgotten/")
    def forgotten(request):
        return {"ok": True}

    own = Router(auth=PhoxtailSessionAuth())

    @own.get("/")
    def under_its_own_router(request):
        return {"ok": True}

    probe.add_router("/own/", own)
    return TestClient(probe)


def _bearer(token):
    return {"Authorization": f"Bearer {token._raw_token}"}


def test_a_superuser_session_is_refused():
    response = _client().get("/forgotten/", user=UserFactory(is_superuser=True))

    assert response.status_code == 403
    assert "has not named the permission" in response.json()["detail"]


def test_an_unrestricted_token_is_refused():
    response = _client().get("/forgotten/", headers=_bearer(AccessTokenFactory(unrestricted=True)))

    assert response.status_code == 403


def test_a_scoped_token_is_refused():
    token = AccessTokenFactory(unrestricted=False, scopes=["wagtailcore.publish_page"])

    assert _client().get("/forgotten/", headers=_bearer(token)).status_code == 403


def test_an_anonymous_caller_is_still_401_not_403():
    """A missing credential and a refused one stay different answers."""
    assert _client().get("/forgotten/").status_code == 401


def test_the_refusal_names_every_way_to_open_it():
    detail = _client().get("/forgotten/", user=UserFactory()).json()["detail"]

    for way in ("guarded(", "scoped(", "authenticated()"):
        assert way in detail


def test_a_router_that_declares_its_own_auth_is_not_the_default():
    """What the default does not reach: a router's ``auth=`` replaces it."""
    assert _client().get("/own/", user=UserFactory()).status_code == 200
