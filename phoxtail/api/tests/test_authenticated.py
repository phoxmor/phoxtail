"""`authenticated()` says a door is open, where silence would lock it.

An endpoint declaring no `auth=` keeps the API-wide default, which admits a
session or an unrestricted token and refuses a scoped one. That is the right
answer for an endpoint someone forgot: forgetting should cost a caller access,
never cost everyone safety.

It is the wrong answer for an endpoint that genuinely asks for nothing, and
until this existed the two were written identically — as silence. So a door
meant to stand open was shut to every narrowed credential in the project, and
no session-authenticated test could see it.

The property worth protecting is therefore the *opposite* of the one
`test_scope_enforcement.py` protects: not that an unannotated endpoint refuses
a scoped token, but that this one does not.
"""

from __future__ import annotations

import pytest
from django.test import RequestFactory

from phoxtail.api.auth import Authorize, PhoxtailSessionAuth, authenticated
from phoxtail.tokens.ninja import PhoxtailTokenAuth
from phoxtail.tokens.tests.factories import AccessTokenFactory, UserFactory

pytestmark = pytest.mark.django_db

UNRELATED = "phoxtail_streams.view_block"


def _request(token):
    return RequestFactory().get("/api/", HTTP_AUTHORIZATION=f"Bearer {token._raw_token}")


class TestWhoItAdmits:
    """Every credential, whatever ceiling it carries."""

    def test_an_unrestricted_token_is_admitted(self):
        user = UserFactory()
        token = AccessTokenFactory(user=user)
        assert authenticated()[0](_request(token)).user == user

    def test_a_scoped_token_is_admitted(self):
        """The whole reason this function exists.

        Under the API-wide default this caller is refused, which is why an
        endpoint that means "open" cannot say so by staying silent.
        """
        user = UserFactory()
        token = AccessTokenFactory(user=user, unrestricted=False, scopes=[UNRELATED])
        assert authenticated()[0](_request(token)).user == user

    def test_a_token_naming_nothing_at_all_is_admitted(self):
        """Narrowed to an empty scope list is still narrowed."""
        user = UserFactory()
        token = AccessTokenFactory(user=user, unrestricted=False, scopes=[])
        assert authenticated()[0](_request(token)).user == user

    def test_holding_no_permission_is_irrelevant(self):
        """There is no permission to hold. A fresh account passes."""
        user = UserFactory()
        assert user.get_all_permissions() == set()
        assert authenticated()[0](_request(AccessTokenFactory(user=user))).user == user


class TestWhoItStillRefuses:
    """It is not ``auth=None``, and the difference is the whole safety margin."""

    def test_a_caller_that_resolves_to_nobody_is_not_admitted(self):
        """Returning None lets ninja fall through the stack and answer 401.

        ``auth=None`` would opt out of authentication itself and publish the
        endpoint to anyone at all. This still runs the authenticators.
        """
        assert authenticated()[0](RequestFactory().get("/api/")) is None

    def test_an_invalid_token_is_not_admitted(self):
        request = RequestFactory().get("/api/", HTTP_AUTHORIZATION="Bearer phxt_nope")
        assert authenticated()[0](request) is None

    def test_a_revoked_token_is_not_admitted(self):
        from django.utils import timezone

        user = UserFactory()
        token = AccessTokenFactory(user=user, revoked_at=timezone.now())
        assert authenticated()[0](_request(token)) is None


class TestTheStackItBuilds:
    """Both backends, or a browser session silently stops being served."""

    def test_it_wraps_both_authenticators(self):
        stack = authenticated()
        assert len(stack) == 2
        assert all(isinstance(entry, Authorize) for entry in stack)
        assert isinstance(stack[0].authenticator, PhoxtailTokenAuth)
        assert isinstance(stack[1].authenticator, PhoxtailSessionAuth)

    def test_it_takes_no_codenames(self):
        """A codename would be a check, and the point is that there is none.

        If a future caller wants to name one, that endpoint wants scoped()
        or guarded() instead — which is the line that keeps this from
        becoming the easy way out of a 403.
        """
        with pytest.raises(TypeError):
            authenticated("wagtailcore.view_page")  # type: ignore[call-arg]
