import pytest
from django.utils import timezone

from phoxtail.tokens.services import AccessTokenService

from .factories import AccessTokenFactory

pytestmark = pytest.mark.django_db


class TestRevokeValidation:
    def test_unbound_service_raises(self):
        with pytest.raises(ValueError, match="bound token"):
            AccessTokenService().admin.revoke()


class TestRevokePerform:
    def test_sets_revoked_at(self, access_token):
        assert access_token.revoked_at is None
        AccessTokenService(token=access_token).admin.revoke()
        access_token.refresh_from_db()
        assert access_token.revoked_at is not None

    def test_persists_to_db(self, access_token):
        AccessTokenService(token=access_token).admin.revoke()
        access_token.refresh_from_db()
        assert access_token.revoked_at is not None

    def test_returns_token_instance(self, access_token):
        result = AccessTokenService(token=access_token).admin.revoke()
        assert result is access_token

    def test_in_memory_instance_reflects_revocation(self, access_token):
        AccessTokenService(token=access_token).admin.revoke()
        # Service mutates the bound instance so callers can show "revoked"
        # status in the same response without an extra DB read.
        assert access_token.revoked_at is not None


class TestRevokeIdempotent:
    def test_re_revoke_preserves_original_timestamp(self, user):
        original = (
            timezone.now() - timezone.timedelta(days=1)
            if hasattr(timezone, "timedelta")
            else None
        )
        # Build a token already revoked at a known past time.
        from datetime import timedelta

        original = timezone.now() - timedelta(days=1)
        token = AccessTokenFactory(user=user, revoked_at=original)
        AccessTokenService(token=token).admin.revoke()
        token.refresh_from_db()
        assert token.revoked_at == original

    def test_double_revoke_still_revoked(self, access_token):
        AccessTokenService(token=access_token).admin.revoke()
        first = access_token.revoked_at
        AccessTokenService(token=access_token).admin.revoke()
        access_token.refresh_from_db()
        assert access_token.revoked_at == first
