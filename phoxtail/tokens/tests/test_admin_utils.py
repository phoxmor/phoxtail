import pytest
from django.test import RequestFactory

from phoxtail.tokens.models import AccessToken

from .conftest import grant_token_permissions
from .factories import AccessTokenFactory

pytestmark = pytest.mark.django_db


# Deferred import: phoxtail.tokens.admin.utils imports from
# phoxtail.tokens.filters, whose module-level get_search_backend() call
# touches the DB. Importing at collection-time would fail before
# pytest-django sets up the test database.
def _utils():
    from phoxtail.tokens.admin.utils import (
        PAGE_SIZE,
        AccessTokensContextBuilder,
        can_user_revoke,
    )

    return PAGE_SIZE, AccessTokensContextBuilder, can_user_revoke


@pytest.fixture
def PAGE_SIZE():
    return _utils()[0]


@pytest.fixture
def AccessTokensContextBuilder():
    return _utils()[1]


@pytest.fixture
def can_user_revoke():
    return _utils()[2]


# ─────────────────────────────────────────────────────────
# can_user_revoke
# ─────────────────────────────────────────────────────────
class TestCanUserRevoke:
    def test_user_without_revoke_permission_cannot_revoke_own(self, user, access_token, can_user_revoke):
        req = RequestFactory().get("/")
        req.user = user
        assert can_user_revoke(req, access_token) is False

    def test_user_with_revoke_permission_can_revoke_own(self, user, access_token, can_user_revoke):
        u = grant_token_permissions(user, "revoke_access_tokens")
        req = RequestFactory().get("/")
        req.user = u
        assert can_user_revoke(req, access_token) is True

    def test_user_with_revoke_only_cannot_revoke_others(self, user, other_user, can_user_revoke):
        token = AccessTokenFactory(user=other_user)
        u = grant_token_permissions(user, "revoke_access_tokens")
        req = RequestFactory().get("/")
        req.user = u
        assert can_user_revoke(req, token) is False

    def test_user_with_manage_all_can_revoke_others(self, user, other_user, can_user_revoke):
        token = AccessTokenFactory(user=other_user)
        u = grant_token_permissions(user, "revoke_access_tokens", "manage_all_tokens")
        req = RequestFactory().get("/")
        req.user = u
        assert can_user_revoke(req, token) is True

    def test_manage_all_alone_is_insufficient(self, user, other_user, can_user_revoke):
        token = AccessTokenFactory(user=other_user)
        u = grant_token_permissions(user, "manage_all_tokens")
        req = RequestFactory().get("/")
        req.user = u
        assert can_user_revoke(req, token) is False

    def test_superuser_can_revoke_anything(self, superuser, other_user, can_user_revoke):
        token = AccessTokenFactory(user=other_user)
        req = RequestFactory().get("/")
        req.user = superuser
        assert can_user_revoke(req, token) is True


# ─────────────────────────────────────────────────────────
# AccessTokensContextBuilder
# ─────────────────────────────────────────────────────────
class TestContextBuilderScoping:
    def test_self_only_for_user_without_manage_all(self, user, other_user, AccessTokensContextBuilder):
        AccessTokenFactory(user=user, name="mine")
        AccessTokenFactory(user=other_user, name="theirs")
        req = RequestFactory().get("/")
        req.user = user
        ctx = AccessTokensContextBuilder.get_full_context(req)
        names = {t.name for t in ctx["tokens"].object_list}
        assert names == {"mine"}
        assert ctx["total_tokens"] == 1
        assert ctx["can_manage_all"] is False

    def test_org_wide_for_user_with_manage_all(self, user, other_user, AccessTokensContextBuilder):
        AccessTokenFactory(user=user, name="mine")
        AccessTokenFactory(user=other_user, name="theirs")
        u = grant_token_permissions(user, "manage_all_tokens")
        req = RequestFactory().get("/")
        req.user = u
        ctx = AccessTokensContextBuilder.get_full_context(req)
        names = {t.name for t in ctx["tokens"].object_list}
        assert names == {"mine", "theirs"}
        assert ctx["total_tokens"] == 2
        assert ctx["can_manage_all"] is True

    def test_superuser_sees_all(self, superuser, user, other_user, AccessTokensContextBuilder):
        AccessTokenFactory(user=user, name="mine")
        AccessTokenFactory(user=other_user, name="theirs")
        req = RequestFactory().get("/")
        req.user = superuser
        ctx = AccessTokensContextBuilder.get_full_context(req)
        assert ctx["total_tokens"] == 2
        assert ctx["can_manage_all"] is True


class TestContextBuilderPermissionFlags:
    def test_can_create_reflects_permission(self, user, AccessTokensContextBuilder):
        req = RequestFactory().get("/")
        req.user = user
        ctx = AccessTokensContextBuilder.get_full_context(req)
        assert ctx["can_create"] is False

        u = grant_token_permissions(user, "create_access_tokens")
        req2 = RequestFactory().get("/")
        req2.user = u
        ctx2 = AccessTokensContextBuilder.get_full_context(req2)
        assert ctx2["can_create"] is True

    def test_can_revoke_reflects_permission(self, user, AccessTokensContextBuilder):
        req = RequestFactory().get("/")
        req.user = user
        ctx = AccessTokensContextBuilder.get_full_context(req)
        assert ctx["can_revoke"] is False

        u = grant_token_permissions(user, "revoke_access_tokens")
        req2 = RequestFactory().get("/")
        req2.user = u
        ctx2 = AccessTokensContextBuilder.get_full_context(req2)
        assert ctx2["can_revoke"] is True


class TestContextBuilderPagination:
    def test_pagination_limits_tokens(self, user, PAGE_SIZE, AccessTokensContextBuilder):
        for _ in range(PAGE_SIZE + 5):
            AccessTokenFactory(user=user)
        req = RequestFactory().get("/")
        req.user = user
        ctx = AccessTokensContextBuilder.get_full_context(req)
        assert len(ctx["tokens"].object_list) == PAGE_SIZE
        assert ctx["total_tokens"] == PAGE_SIZE + 5

    def test_page_param_advances(self, user, PAGE_SIZE, AccessTokensContextBuilder):
        for _ in range(PAGE_SIZE + 3):
            AccessTokenFactory(user=user)
        req = RequestFactory().get("/", {"filter-page": "2"})
        req.user = user
        ctx = AccessTokensContextBuilder.get_full_context(req)
        assert ctx["tokens"].number == 2
        assert len(ctx["tokens"].object_list) == 3


class TestContextBuilderFilterCount:
    def test_filter_count_excludes_search_and_page(self, user, AccessTokensContextBuilder):
        AccessTokenFactory(user=user)
        req = RequestFactory().get("/", {"filter-search": "x", "filter-page": "1", "filter-status": "active"})
        req.user = user
        ctx = AccessTokensContextBuilder.get_full_context(req)
        # Only status counts.
        assert ctx["filter_count"] == 1

    def test_filter_count_zero_with_no_filters(self, user, AccessTokensContextBuilder):
        req = RequestFactory().get("/")
        req.user = user
        ctx = AccessTokensContextBuilder.get_full_context(req)
        assert ctx["filter_count"] == 0


class TestFiltersContext:
    def test_filters_context_does_not_load_tokens(self, user, AccessTokensContextBuilder):
        AccessTokenFactory(user=user)
        req = RequestFactory().get("/")
        req.user = user
        ctx = AccessTokensContextBuilder.get_filters_context(req)
        assert "tokens" not in ctx
        assert "filterset" in ctx
        assert "filter_count" in ctx
        assert "can_manage_all" in ctx


class TestPostMethodReadsPostParams:
    def test_post_uses_post_params_for_filters(self, user, AccessTokensContextBuilder):
        AccessTokenFactory(user=user)
        req = RequestFactory().post("/", {"filter-status": "active"})
        req.user = user
        ctx = AccessTokensContextBuilder.get_full_context(req)
        assert ctx["filter_count"] == 1


class TestQuerysetIsolation:
    def test_no_query_when_listing_with_no_tokens(self, user, AccessTokensContextBuilder):
        # Sanity: builder should still resolve cleanly with empty DB.
        req = RequestFactory().get("/")
        req.user = user
        ctx = AccessTokensContextBuilder.get_full_context(req)
        assert AccessToken.objects.count() == 0
        assert ctx["total_tokens"] == 0
