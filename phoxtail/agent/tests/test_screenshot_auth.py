"""The screenshot view's query-parameter authentication.

Playwright cannot set request headers while navigating, so this one view
accepts ``?token=`` instead of an Authorization header. That makes it the
only place outside the Ninja adapter that consumes
``phoxtail.tokens.auth.authenticate`` directly — and therefore the only
place a change to what that function returns can go wrong unnoticed.

It nearly did: ``authenticate`` now resolves an ``AccessToken`` rather
than a ``User``, and ``AccessToken`` happens to expose ``is_active``. A
permission policy checking ``is_active`` first would pass that check on
the wrong object and fail only on the next attribute — a late, confusing
failure instead of an immediate one. These tests pin the contract so the
next change to that seam breaks loudly.
"""

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType

from phoxtail.agent.permissions.models import AgentAdminPermission
from phoxtail.agent.views import _authenticate_screenshot_request
from phoxtail.tokens.tests.factories import AccessTokenFactory, UserFactory

User = get_user_model()
pytestmark = pytest.mark.django_db


def _request(rf, token: str | None):
    return rf.get("/screenshot/", {"token": token} if token is not None else {})


def _with_chatbot_access(user):
    ct = ContentType.objects.get_for_model(AgentAdminPermission)
    perm = Permission.objects.get(content_type=ct, codename="access_chatbot")
    user.user_permissions.add(perm)
    # has_perm results are cached on the instance; re-fetch to see the grant.
    return User.objects.get(pk=user.pk)


class TestScreenshotAuthentication:
    def test_returns_the_user_not_the_token(self, rf):
        """The view's callers expect a person. Returning the credential
        would put an AccessToken where a User is used."""
        user = _with_chatbot_access(UserFactory())
        token = AccessTokenFactory(user=user)

        result = _authenticate_screenshot_request(_request(rf, token._raw_token))

        assert result == user
        assert isinstance(result, User)

    def test_refuses_a_valid_token_whose_user_lacks_chatbot_access(self, rf):
        """Authenticated is not authorized. This is the assertion that
        catches a permission check accidentally run against the token."""
        token = AccessTokenFactory(user=UserFactory())
        assert _authenticate_screenshot_request(_request(rf, token._raw_token)) is None

    def test_refuses_an_unknown_token(self, rf):
        assert _authenticate_screenshot_request(_request(rf, "phxt_zzznosuchtokennosuchtoken")) is None

    def test_refuses_a_missing_token(self, rf):
        assert _authenticate_screenshot_request(_request(rf, None)) is None

    def test_refuses_a_revoked_token(self, rf):
        from django.utils import timezone

        user = _with_chatbot_access(UserFactory())
        token = AccessTokenFactory(user=user, revoked_at=timezone.now())
        assert _authenticate_screenshot_request(_request(rf, token._raw_token)) is None
