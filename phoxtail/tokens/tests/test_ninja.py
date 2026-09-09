import pytest
from django.test import RequestFactory

from phoxtail.core.authorization import AuthorizationContext
from phoxtail.tokens.ninja import PhoxtailTokenAuth

pytestmark = pytest.mark.django_db


@pytest.fixture
def auth():
    return PhoxtailTokenAuth()


@pytest.fixture
def req():
    return RequestFactory().get("/api/")


class TestPhoxtailTokenAuth:
    def test_returns_context_for_bearer_with_valid_token(self, auth, req, access_token):
        result = auth.authenticate(req, f"Bearer {access_token._raw_token}")
        assert isinstance(result, AuthorizationContext)
        assert result.user == access_token.user
        assert result.token == access_token

    def test_returns_none_for_missing_bearer_prefix(self, auth, req, access_token):
        assert auth.authenticate(req, access_token._raw_token) is None

    def test_returns_none_for_wrong_scheme(self, auth, req, access_token):
        assert auth.authenticate(req, f"Basic {access_token._raw_token}") is None

    def test_returns_none_for_empty_key(self, auth, req):
        assert auth.authenticate(req, "") is None
        assert auth.authenticate(req, None) is None

    def test_returns_none_for_unknown_token(self, auth, req):
        assert auth.authenticate(req, "Bearer phxt_zzznosuchtokennosuchtokennosuchto") is None

    def test_param_name_is_authorization(self, auth):
        assert auth.param_name == "Authorization"


class TestSessionAuthResolvesTheSameShape:
    """Endpoints must not have to care how the caller logged in.

    A browser session carries no credential to narrow the user by, so its
    context has ``token=None`` — but it is still a context. Two different
    ``request.auth`` shapes depending on the login path is exactly the
    branching this object exists to remove.
    """

    def test_session_login_resolves_a_context_without_a_token(self, req, user):
        from phoxtail.api.auth import PhoxtailSessionAuth

        req.user = user
        result = PhoxtailSessionAuth().authenticate(req, None)
        assert isinstance(result, AuthorizationContext)
        assert result.token is None
        # `is`, not `==`: the context stores the object the backend
        # resolved, so every consumer receives exactly what it received
        # before this indirection existed — including the lazy user
        # object Django attaches to a session request.
        assert result.user is user

    def test_anonymous_session_resolves_nothing(self, req):
        from django.contrib.auth.models import AnonymousUser

        from phoxtail.api.auth import PhoxtailSessionAuth

        req.user = AnonymousUser()
        assert PhoxtailSessionAuth().authenticate(req, None) is None
