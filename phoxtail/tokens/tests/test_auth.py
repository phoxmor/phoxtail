import hashlib
from datetime import timedelta

import pytest
from django.utils import timezone
from freezegun import freeze_time

from phoxtail.tokens.auth import authenticate
from phoxtail.tokens.models import AccessToken

from .factories import AccessTokenFactory

pytestmark = pytest.mark.django_db


class TestAuthenticateInputValidation:
    @pytest.mark.parametrize("raw", ["", None, "short"])
    def test_returns_none_for_invalid_input(self, raw):
        assert authenticate(raw) is None

    def test_returns_none_for_unknown_token(self):
        assert authenticate("phxt_AAAxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx") is None


class TestAuthenticateValidToken:
    def test_returns_user_for_valid_raw(self, access_token):
        result = authenticate(access_token._raw_token)
        assert result is not None
        assert result.pk == access_token.user.pk

    def test_digest_lookup_uses_sha256_hex(self, access_token):
        expected = hashlib.sha256(access_token._raw_token.encode()).hexdigest()
        assert access_token.digest == expected

    def test_returns_none_for_revoked_token(self, user):
        token = AccessTokenFactory(user=user, revoked_at=timezone.now())
        assert authenticate(token._raw_token) is None

    def test_returns_none_for_expired_token(self, user):
        token = AccessTokenFactory(user=user, expires_at=timezone.now() - timedelta(minutes=1))
        assert authenticate(token._raw_token) is None

    def test_returns_token_when_expiry_in_future(self, user):
        token = AccessTokenFactory(user=user, expires_at=timezone.now() + timedelta(days=1))
        assert authenticate(token._raw_token) == token

    def test_returns_the_credential_not_its_owner(self, user):
        """The caller needs the token's scopes and type, not only who owns
        it — returning the user is what discarded that for years."""
        token = AccessTokenFactory(user=user)
        resolved = authenticate(token._raw_token)
        assert resolved.pk == token.pk
        assert resolved.user == user


class TestLastUsedThrottle:
    def test_first_use_sets_last_used_at(self, access_token):
        assert access_token.last_used_at is None
        authenticate(access_token._raw_token)
        access_token.refresh_from_db()
        assert access_token.last_used_at is not None

    def test_repeated_use_within_throttle_does_not_update(self, access_token):
        with freeze_time("2026-01-01 12:00:00"):
            authenticate(access_token._raw_token)
            access_token.refresh_from_db()
            first = access_token.last_used_at
        with freeze_time("2026-01-01 12:00:30"):
            authenticate(access_token._raw_token)
            access_token.refresh_from_db()
            assert access_token.last_used_at == first

    def test_use_past_throttle_window_updates(self, access_token):
        with freeze_time("2026-01-01 12:00:00"):
            authenticate(access_token._raw_token)
            access_token.refresh_from_db()
            first = access_token.last_used_at
        with freeze_time("2026-01-01 12:02:00"):
            authenticate(access_token._raw_token)
            access_token.refresh_from_db()
            assert access_token.last_used_at > first


class TestAuthenticateNoSideEffects:
    def test_unknown_token_does_not_create_rows(self, db):
        before = AccessToken.objects.count()
        authenticate("phxt_BBBbogusbogusbogusbogusbogusbogusbg")
        assert AccessToken.objects.count() == before

    def test_invalid_input_does_not_query(self, django_assert_num_queries):
        with django_assert_num_queries(0):
            authenticate("")
        with django_assert_num_queries(0):
            authenticate(None)
        with django_assert_num_queries(0):
            authenticate("abc")
