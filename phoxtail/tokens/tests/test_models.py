from datetime import timedelta

import pytest
from django.db import IntegrityError
from django.utils import timezone

from .factories import AccessTokenFactory

pytestmark = pytest.mark.django_db


class TestAccessTokenStr:
    def test_str_contains_name_prefix_and_suffix(self, access_token):
        s = str(access_token)
        assert access_token.name in s
        assert access_token.prefix in s
        assert access_token.suffix in s


class TestAccessTokenIsActive:
    def test_active_when_not_revoked_and_no_expiry(self, access_token):
        assert access_token.is_active is True

    def test_inactive_when_revoked(self, user):
        token = AccessTokenFactory(user=user, revoked_at=timezone.now())
        assert token.is_active is False

    def test_inactive_when_expired(self, user):
        token = AccessTokenFactory(user=user, expires_at=timezone.now() - timedelta(seconds=1))
        assert token.is_active is False

    def test_active_with_future_expiry(self, user):
        token = AccessTokenFactory(user=user, expires_at=timezone.now() + timedelta(days=1))
        assert token.is_active is True

    def test_revocation_beats_future_expiry(self, user):
        token = AccessTokenFactory(
            user=user,
            expires_at=timezone.now() + timedelta(days=1),
            revoked_at=timezone.now(),
        )
        assert token.is_active is False


class TestAccessTokenProxyAttributes:
    def test_user_email_proxy(self, access_token):
        assert access_token.user_email == access_token.user.email

    def test_user_username_proxy(self, access_token):
        assert access_token.user_username == access_token.user.username

    def test_user_first_name_proxy(self, access_token, user):
        user.first_name = "Ada"
        user.save()
        access_token.refresh_from_db()
        assert access_token.user_first_name == "Ada"

    def test_user_last_name_proxy(self, access_token, user):
        user.last_name = "Lovelace"
        user.save()
        access_token.refresh_from_db()
        assert access_token.user_last_name == "Lovelace"


class TestAccessTokenIntegrity:
    def test_digest_is_unique(self, user):
        token = AccessTokenFactory(user=user)
        with pytest.raises(IntegrityError):
            AccessTokenFactory(user=user, raw_token=token._raw_token)

    def test_default_ordering_is_recent_first(self, user):
        older = AccessTokenFactory(user=user)
        newer = AccessTokenFactory(user=user)
        # auto_now_add timestamps may collide; force order
        from phoxtail.tokens.models import AccessToken

        AccessToken.objects.filter(pk=older.pk).update(created_at=timezone.now() - timedelta(days=1))
        ordered = list(AccessToken.objects.values_list("pk", flat=True))
        assert ordered[0] == newer.pk
        assert ordered[-1] == older.pk
