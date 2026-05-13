"""
Tests for permission_required_factory — the FBV decorator factory.

Each test exercises a single concern: the decorator correctly blocks or
allows requests, and handles HTMX vs regular requests differently.
"""

import pytest
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse

from phoxtail.core.permissions import permission_required_factory
from phoxtail.core.tests.conftest import grant_permissions

pytestmark = pytest.mark.django_db


@pytest.fixture
def decorator(policy):
    return permission_required_factory(policy)


def _dummy_view(request):
    return HttpResponse("ok")


class TestPermissionRequired:
    """Tests for the decorator produced by permission_required_factory."""

    def test_allows_when_user_has_permission(self, decorator, user, rf):
        user = grant_permissions(user, "access_test_management")
        view = decorator("access_test_management")(_dummy_view)
        request = rf.get("/")
        request.user = user
        response = view(request)
        assert response.status_code == 200

    def test_raises_permission_denied_when_user_lacks_permission(self, decorator, user, rf):
        view = decorator("access_test_management")(_dummy_view)
        request = rf.get("/")
        request.user = user
        with pytest.raises(PermissionDenied):
            view(request)

    def test_superuser_always_passes(self, decorator, superuser, rf):
        view = decorator("access_test_management", "manage_test_items")(_dummy_view)
        request = rf.get("/")
        request.user = superuser
        response = view(request)
        assert response.status_code == 200

    def test_requires_all_listed_permissions(self, decorator, user, rf):
        user = grant_permissions(user, "access_test_management")
        view = decorator("access_test_management", "manage_test_items")(_dummy_view)
        request = rf.get("/")
        request.user = user
        with pytest.raises(PermissionDenied):
            view(request)

    def test_passes_when_all_listed_permissions_granted(self, decorator, user, rf):
        user = grant_permissions(user, "access_test_management", "manage_test_items")
        view = decorator("access_test_management", "manage_test_items")(_dummy_view)
        request = rf.get("/")
        request.user = user
        response = view(request)
        assert response.status_code == 200


class TestHTMXHandling:
    """Tests for HTMX-specific 403 response (no redirect)."""

    def test_htmx_request_returns_204_with_toast_event(self, decorator, user, rf):
        view = decorator("access_test_management")(_dummy_view)
        request = rf.get("/", HTTP_HX_REQUEST="true")
        request.user = user
        response = view(request)
        assert response.status_code == 204
        assert "showToast" in response["HX-Trigger"]

    def test_non_htmx_request_raises_permission_denied(self, decorator, user, rf):
        view = decorator("access_test_management")(_dummy_view)
        request = rf.get("/")
        request.user = user
        with pytest.raises(PermissionDenied):
            view(request)

    def test_htmx_request_with_permission_passes(self, decorator, user, rf):
        user = grant_permissions(user, "access_test_management")
        view = decorator("access_test_management")(_dummy_view)
        request = rf.get("/", HTTP_HX_REQUEST="true")
        request.user = user
        response = view(request)
        assert response.status_code == 200


class TestDecoratorPreservesFunction:
    """Tests that the decorator preserves the wrapped function's metadata."""

    def test_preserves_function_name(self, decorator):
        @decorator("access_test_management")
        def my_special_view(request):
            return HttpResponse("ok")

        assert my_special_view.__name__ == "my_special_view"

    def test_preserves_function_module(self, decorator):
        @decorator("access_test_management")
        def my_special_view(request):
            return HttpResponse("ok")

        assert my_special_view.__module__ == __name__
