"""
Tests for PermissionMixin — the generic CBV mixin for permission-protected views.

Each test exercises a single concern: the mixin correctly blocks or allows
requests, handles HTMX vs regular requests, and is a no-op when
permission_policy is None.
"""

import pytest
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.views import View

from phoxtail.core.permissions import PermissionMixin
from phoxtail.core.tests.conftest import grant_permissions

pytestmark = pytest.mark.django_db


class _BaseView(View):
    def get(self, request):
        return HttpResponse("ok")


class TestPermissionMixin:
    """Tests for PermissionMixin.dispatch() enforcement."""

    def _make_view(self, policy=None, perms=None):
        class TestView(PermissionMixin, _BaseView):
            permission_policy = policy
            required_permissions = perms or []

        return TestView.as_view()

    def test_allows_when_user_has_required_permission(self, policy, user, rf):
        user = grant_permissions(user, "access_test_management")
        view = self._make_view(policy, ["access_test_management"])
        request = rf.get("/")
        request.user = user
        response = view(request)
        assert response.status_code == 200

    def test_denies_when_user_lacks_permission(self, policy, user, rf):
        view = self._make_view(policy, ["access_test_management"])
        request = rf.get("/")
        request.user = user
        with pytest.raises(PermissionDenied):
            view(request)

    def test_requires_all_listed_permissions(self, policy, user, rf):
        user = grant_permissions(user, "access_test_management")
        view = self._make_view(policy, ["access_test_management", "manage_test_items"])
        request = rf.get("/")
        request.user = user
        with pytest.raises(PermissionDenied):
            view(request)

    def test_passes_when_all_permissions_granted(self, policy, user, rf):
        user = grant_permissions(user, "access_test_management", "manage_test_items")
        view = self._make_view(policy, ["access_test_management", "manage_test_items"])
        request = rf.get("/")
        request.user = user
        response = view(request)
        assert response.status_code == 200

    def test_superuser_always_passes(self, policy, superuser, rf):
        view = self._make_view(policy, ["access_test_management", "manage_test_items"])
        request = rf.get("/")
        request.user = superuser
        response = view(request)
        assert response.status_code == 200


class TestNoOpWhenPolicyIsNone:
    """Tests that mixin is a no-op when permission_policy is None."""

    def test_allows_any_user_when_no_policy(self, user, rf):
        class TestView(PermissionMixin, _BaseView):
            permission_policy = None
            required_permissions = ["access_test_management"]

        view = TestView.as_view()
        request = rf.get("/")
        request.user = user
        response = view(request)
        assert response.status_code == 200

    def test_allows_when_no_policy_and_no_permissions(self, user, rf):
        class TestView(PermissionMixin, _BaseView):
            pass

        view = TestView.as_view()
        request = rf.get("/")
        request.user = user
        response = view(request)
        assert response.status_code == 200


class TestHTMXHandling:
    """Tests for HTMX-specific 403 response."""

    def _make_view(self, policy, perms):
        class TestView(PermissionMixin, _BaseView):
            permission_policy = policy
            required_permissions = perms

        return TestView.as_view()

    def test_htmx_request_returns_204_with_toast_event(self, policy, user, rf):
        view = self._make_view(policy, ["access_test_management"])
        request = rf.get("/", HTTP_HX_REQUEST="true")
        request.user = user
        response = view(request)
        assert response.status_code == 204
        assert "showToast" in response["HX-Trigger"]

    def test_non_htmx_request_raises_permission_denied(self, policy, user, rf):
        view = self._make_view(policy, ["access_test_management"])
        request = rf.get("/")
        request.user = user
        with pytest.raises(PermissionDenied):
            view(request)

    def test_htmx_request_with_permission_passes(self, policy, user, rf):
        user = grant_permissions(user, "access_test_management")
        view = self._make_view(policy, ["access_test_management"])
        request = rf.get("/", HTTP_HX_REQUEST="true")
        request.user = user
        response = view(request)
        assert response.status_code == 200
