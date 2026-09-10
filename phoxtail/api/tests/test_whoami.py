"""``GET /api/whoami/`` — what a credential is, to a caller that cannot read it.

The MCP server forwards an opaque Bearer and is, by design, never the
authority on what it contains. This endpoint is how it asks the authority
instead of deciding for itself.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from django.test import RequestFactory

from phoxtail.api import api, whoami
from phoxtail.api.auth import Authorize
from phoxtail.core.authorization import AuthorizationContext
from phoxtail.tokens.ninja import PhoxtailTokenAuth
from phoxtail.tokens.tests.factories import AccessTokenFactory, UserFactory

pytestmark = pytest.mark.django_db

PUBLISH = "wagtailcore.publish_page"


def _call(context):
    return whoami(SimpleNamespace(auth=context))


class TestWhatItReports:
    def test_a_scoped_token_sees_its_own_ceiling(self):
        user = UserFactory()
        token = AccessTokenFactory(user=user, unrestricted=False, scopes=[PUBLISH])

        result = _call(AuthorizationContext(user=user, token=token))

        assert result["username"] == user.get_username()
        assert result["user_uuid"] == user.uuid
        assert result["unrestricted"] is False
        assert result["scopes"] == [PUBLISH]

    def test_an_unrestricted_token_reports_no_ceiling(self):
        user = UserFactory()
        token = AccessTokenFactory(user=user, unrestricted=True)

        result = _call(AuthorizationContext(user=user, token=token))

        assert result["unrestricted"] is True
        assert result["scopes"] == []

    def test_a_session_reports_no_ceiling_and_no_expiry(self):
        """A browser session carries no credential to narrow or to expire,
        so it answers the same as an unrestricted token — which is exactly
        how the rest of the system treats it."""
        user = UserFactory()

        result = _call(AuthorizationContext(user=user))

        assert result["unrestricted"] is True
        assert result["scopes"] == []
        assert result["expires_at"] is None

    def test_superuser_is_reported_separately_from_the_ceiling(self):
        """Who you are and what your key permits are different answers, and
        a caller planning its next call needs both."""
        user = UserFactory(is_superuser=True)
        token = AccessTokenFactory(user=user, unrestricted=False, scopes=[PUBLISH])

        result = _call(AuthorizationContext(user=user, token=token))

        assert result["is_superuser"] is True
        assert result["unrestricted"] is False


class TestItIsReachableByEveryCredential:
    """A caller cannot discover its own limits if the endpoint that reports
    them sits behind those limits. This is the one endpoint that must opt
    out of closed-by-default."""

    @staticmethod
    def _operation():
        for path, po in api.default_router.path_operations.items():
            if path == "/whoami/":
                return po.operations[0]
        raise AssertionError("/whoami/ is not registered")

    def test_it_declares_its_own_auth_rather_than_inheriting(self):
        assert self._operation().auth_callbacks, "would inherit the scoped-token refusal"

    def test_none_of_its_backends_apply_a_predicate(self):
        assert not [cb for cb in self._operation().auth_callbacks if isinstance(cb, Authorize)]

    def test_a_scoped_token_is_admitted(self):
        user = UserFactory()
        token = AccessTokenFactory(user=user, unrestricted=False, scopes=[PUBLISH])
        request = RequestFactory().get("/api/whoami/", HTTP_AUTHORIZATION=f"Bearer {token._raw_token}")

        resolved = PhoxtailTokenAuth().authenticate(request, f"Bearer {token._raw_token}")

        assert resolved.user == user
        assert _call(resolved)["scopes"] == [PUBLISH]
