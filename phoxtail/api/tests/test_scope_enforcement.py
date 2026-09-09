"""Scope enforcement: the credential's half of the authorization question.

A scope asks whether the *credential* a caller arrived with may be used
for this kind of act. Whether the *person* may perform it stays where it
already is, and is often decided far more finely — Wagtail resolves
publishing per page subtree. Both must pass; these tests cover only the
coarse half, because the fine half was already covered where it lives.

The property worth protecting is that an endpoint which declares no scope
is closed to a scoped token rather than open to it. Forgetting to
annotate an endpoint should cost a caller access, never cost everyone
safety.
"""

from __future__ import annotations

import pytest
from django.test import RequestFactory
from ninja.errors import HttpError

from phoxtail.api.auth import Authorize, has_no_ceiling, has_scope, scoped
from phoxtail.core.authorization import AuthorizationContext
from phoxtail.tokens.ninja import PhoxtailTokenAuth
from phoxtail.tokens.tests.factories import AccessTokenFactory, UserFactory

pytestmark = pytest.mark.django_db

PUBLISH = "wagtailcore.publish_page"
VIEW_SITE = "wagtailcore.view_site"


def _session(user):
    """A browser session: a person, and no credential narrowing them."""
    return AuthorizationContext(user=user)


def _unrestricted(user):
    # Explicit rather than relying on the factory default: these three
    # helpers are the whole subject of this file, and a factory edit must
    # not silently change which case a test covers.
    return AuthorizationContext(user=user, token=AccessTokenFactory(user=user, unrestricted=True))


def _scoped(user, *codenames):
    token = AccessTokenFactory(user=user, unrestricted=False, scopes=list(codenames))
    return AuthorizationContext(user=user, token=token)


class TestHasNoCeiling:
    """What makes an unannotated endpoint closed to some callers and not
    others."""

    def test_a_session_has_none(self, db):
        assert has_no_ceiling(_session(UserFactory())) is True

    def test_an_unrestricted_token_has_none(self, db):
        assert has_no_ceiling(_unrestricted(UserFactory())) is True

    def test_a_scoped_token_has_one(self, db):
        assert has_no_ceiling(_scoped(UserFactory(), PUBLISH)) is False


class TestHasScope:
    def test_a_session_passes_anything(self, db):
        assert has_scope(PUBLISH)(_session(UserFactory())) is True

    def test_an_unrestricted_token_passes_anything(self, db):
        assert has_scope(PUBLISH)(_unrestricted(UserFactory())) is True

    def test_a_matching_scoped_token_passes(self, db):
        assert has_scope(PUBLISH)(_scoped(UserFactory(), PUBLISH)) is True

    def test_a_non_matching_scoped_token_is_refused(self, db):
        assert has_scope(PUBLISH)(_scoped(UserFactory(), VIEW_SITE)) is False

    def test_every_declared_codename_is_required(self, db):
        """A partial match is a refusal: the endpoint said what it needs,
        and half of it is not it."""
        predicate = has_scope(PUBLISH, VIEW_SITE)
        assert predicate(_scoped(UserFactory(), PUBLISH, VIEW_SITE)) is True
        assert predicate(_scoped(UserFactory(), PUBLISH)) is False


class TestScopedHelper:
    def test_accepts_both_token_and_session_callers(self):
        backends = scoped(PUBLISH)
        assert len(backends) == 2
        assert all(isinstance(b, Authorize) for b in backends)

    def test_names_the_missing_scope_in_the_refusal(self):
        assert PUBLISH in scoped(PUBLISH)[0].detail


class TestThroughTheRealBackend:
    """End to end over a real Bearer header, since the predicates above
    are only correct if the backend actually resolves the token onto the
    context they read."""

    @staticmethod
    def _request(token):
        return RequestFactory().get("/api/", HTTP_AUTHORIZATION=f"Bearer {token._raw_token}")

    def test_an_unannotated_endpoint_refuses_a_scoped_token(self):
        user = UserFactory()
        token = AccessTokenFactory(user=user, unrestricted=False, scopes=[PUBLISH])
        backend = Authorize(PhoxtailTokenAuth(), has_no_ceiling, detail="nope")

        with pytest.raises(HttpError) as exc:
            backend(self._request(token))
        assert exc.value.status_code == 403

    def test_an_unannotated_endpoint_admits_an_unrestricted_token(self):
        user = UserFactory()
        token = AccessTokenFactory(user=user)
        backend = Authorize(PhoxtailTokenAuth(), has_no_ceiling, detail="nope")

        assert backend(self._request(token)).user == user

    def test_an_annotated_endpoint_admits_the_matching_scope(self):
        user = UserFactory()
        token = AccessTokenFactory(user=user, unrestricted=False, scopes=[PUBLISH])

        assert scoped(PUBLISH)[0](self._request(token)).user == user

    def test_an_annotated_endpoint_refuses_the_wrong_scope(self):
        user = UserFactory()
        token = AccessTokenFactory(user=user, unrestricted=False, scopes=[VIEW_SITE])

        with pytest.raises(HttpError) as exc:
            scoped(PUBLISH)[0](self._request(token))
        assert exc.value.status_code == 403

    def test_an_invalid_token_is_401_not_403(self):
        """A bad credential and an insufficient one are different answers,
        and a caller needs to tell them apart to know what to fix.
        Returning None lets ninja fall through the auth stack to 401."""
        assert scoped(PUBLISH)[0](RequestFactory().get("/api/", HTTP_AUTHORIZATION="Bearer phxt_nope")) is None
