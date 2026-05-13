import pytest
from django.test import RequestFactory

from phoxtail.tokens.ninja import PhoxtailTokenAuth

pytestmark = pytest.mark.django_db


@pytest.fixture
def auth():
    return PhoxtailTokenAuth()


@pytest.fixture
def req():
    return RequestFactory().get("/api/")


class TestPhoxtailTokenAuth:
    def test_returns_user_for_bearer_with_valid_token(self, auth, req, access_token):
        result = auth.authenticate(req, f"Bearer {access_token._raw_token}")
        assert result == access_token.user

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
