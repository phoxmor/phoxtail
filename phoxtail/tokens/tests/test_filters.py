from datetime import timedelta

import pytest
from django.utils import timezone

from phoxtail.tokens.models import AccessToken

from .factories import AccessTokenFactory

pytestmark = pytest.mark.django_db


# Deferred so ``get_search_backend()`` (executed at module import inside
# phoxtail.tokens.filters) runs *after* pytest-django sets up the test
# database — otherwise importing this test file during collection triggers
# the wagtail SQLite FTS probe and fails with "Database access not allowed".
@pytest.fixture
def TokenFilter():
    from phoxtail.tokens.filters import TokenFilter

    return TokenFilter


@pytest.fixture
def TokenStatus():
    from phoxtail.tokens.filters import TokenStatus

    return TokenStatus


@pytest.fixture
def tokens(user, other_user):
    """A spread of tokens covering every status × ownership combination."""
    return {
        "active_self": AccessTokenFactory(user=user, name="Active Self"),
        "expired_self": AccessTokenFactory(
            user=user,
            name="Expired Self",
            expires_at=timezone.now() - timedelta(days=1),
        ),
        "revoked_self": AccessTokenFactory(user=user, name="Revoked Self", revoked_at=timezone.now()),
        "active_other": AccessTokenFactory(user=other_user, name="Active Other"),
    }


class TestStatusFilter:
    def test_active_only(self, tokens, TokenFilter, TokenStatus):
        qs = AccessToken.objects.all()
        f = TokenFilter({"filter-status": TokenStatus.ACTIVE}, queryset=qs)
        names = set(f.qs.values_list("name", flat=True))
        assert names == {"Active Self", "Active Other"}

    def test_expired_only(self, tokens, TokenFilter, TokenStatus):
        qs = AccessToken.objects.all()
        f = TokenFilter({"filter-status": TokenStatus.EXPIRED}, queryset=qs)
        assert set(f.qs.values_list("name", flat=True)) == {"Expired Self"}

    def test_revoked_only(self, tokens, TokenFilter, TokenStatus):
        qs = AccessToken.objects.all()
        f = TokenFilter({"filter-status": TokenStatus.REVOKED}, queryset=qs)
        assert set(f.qs.values_list("name", flat=True)) == {"Revoked Self"}

    def test_revoked_then_expired_classified_as_revoked(self, user, TokenFilter, TokenStatus):
        AccessTokenFactory(
            user=user,
            name="Both",
            expires_at=timezone.now() - timedelta(days=1),
            revoked_at=timezone.now(),
        )
        qs = AccessToken.objects.all()
        active = TokenFilter({"filter-status": TokenStatus.ACTIVE}, queryset=qs).qs
        expired = TokenFilter({"filter-status": TokenStatus.EXPIRED}, queryset=qs).qs
        revoked = TokenFilter({"filter-status": TokenStatus.REVOKED}, queryset=qs).qs
        assert "Both" not in {t.name for t in active}
        assert "Both" not in {t.name for t in expired}
        assert "Both" in {t.name for t in revoked}

    def test_no_status_returns_all(self, tokens, TokenFilter):
        qs = AccessToken.objects.all()
        f = TokenFilter({}, queryset=qs)
        assert f.qs.count() == qs.count()


class TestSearchFilter:
    def test_blank_search_passes_through(self, tokens, TokenFilter):
        qs = AccessToken.objects.all()
        f = TokenFilter({"filter-search": ""}, queryset=qs)
        assert f.qs.count() == qs.count()


class TestPageFilter:
    def test_page_is_noop(self, tokens, TokenFilter):
        qs = AccessToken.objects.all()
        f = TokenFilter({"filter-page": "2"}, queryset=qs)
        assert f.qs.count() == qs.count()


class TestUserFilterVisibility:
    def test_user_filter_hidden_when_cannot_manage_all(self, TokenFilter):
        f = TokenFilter({}, queryset=AccessToken.objects.all(), can_manage_all=False)
        assert "user" not in f.filters
        assert "user" not in f.form.fields

    def test_user_filter_visible_when_can_manage_all(self, TokenFilter):
        f = TokenFilter({}, queryset=AccessToken.objects.all(), can_manage_all=True)
        assert "user" in f.filters
        assert "user" in f.form.fields

    def test_user_filter_filters_by_owner(self, tokens, user, TokenFilter):
        qs = AccessToken.objects.all()
        f = TokenFilter(
            {"filter-user": str(user.id)},
            queryset=qs,
            can_manage_all=True,
        )
        assert all(t.user_id == user.id for t in f.qs)


class TestPrefix:
    def test_default_prefix_is_filter(self, TokenFilter):
        f = TokenFilter({})
        assert f.form.prefix == "filter"
