"""
Tests for PermissionedViewSet — the base ViewSet with permission-controlled
menu item visibility.

Each test exercises a single concern: the dynamically created MenuItem
subclass correctly shows or hides based on the user's permissions.
"""

import pytest

from phoxtail.core.permissions import PermissionedViewSet
from phoxtail.core.tests.conftest import grant_permissions

pytestmark = pytest.mark.django_db


class TestMenuItemVisibility:
    """Tests for the dynamically created MenuItem's is_shown() method."""

    def _make_viewset(self, policy, perms):
        class TestViewSet(PermissionedViewSet):
            name = "test_viewset"
            permission_policy = policy
            required_permissions = perms

        return TestViewSet()

    def test_menu_hidden_when_user_lacks_permission(self, policy, user, rf):
        vs = self._make_viewset(policy, ["access_test_management"])
        menu_item = vs.menu_item_class("Test", "/test/")
        request = rf.get("/")
        request.user = user
        assert menu_item.is_shown(request) is False

    def test_menu_shown_when_user_has_permission(self, policy, user, rf):
        user = grant_permissions(user, "access_test_management")
        vs = self._make_viewset(policy, ["access_test_management"])
        menu_item = vs.menu_item_class("Test", "/test/")
        request = rf.get("/")
        request.user = user
        assert menu_item.is_shown(request) is True

    def test_menu_shown_for_superuser(self, policy, superuser, rf):
        vs = self._make_viewset(policy, ["access_test_management"])
        menu_item = vs.menu_item_class("Test", "/test/")
        request = rf.get("/")
        request.user = superuser
        assert menu_item.is_shown(request) is True

    def test_menu_shown_when_user_has_any_required_permission(self, policy, user, rf):
        user = grant_permissions(user, "manage_test_items")
        vs = self._make_viewset(policy, ["access_test_management", "manage_test_items"])
        menu_item = vs.menu_item_class("Test", "/test/")
        request = rf.get("/")
        request.user = user
        assert menu_item.is_shown(request) is True


class TestMenuItemFallback:
    """Tests that menu items are always shown when policy or perms are not set."""

    def test_always_shown_when_no_policy(self, user, rf):
        class TestViewSet(PermissionedViewSet):
            name = "test_viewset"
            permission_policy = None
            required_permissions = ["access_test_management"]

        vs = TestViewSet()
        menu_item = vs.menu_item_class("Test", "/test/")
        request = rf.get("/")
        request.user = user
        assert menu_item.is_shown(request) is True

    def test_always_shown_when_no_required_permissions(self, policy, user, rf):
        class TestViewSet(PermissionedViewSet):
            name = "test_viewset"
            permission_policy = policy
            required_permissions = []

        vs = TestViewSet()
        menu_item = vs.menu_item_class("Test", "/test/")
        request = rf.get("/")
        request.user = user
        assert menu_item.is_shown(request) is True


class TestMenuItemClassName:
    """Tests for the dynamically created MenuItem class name."""

    def test_class_name_includes_viewset_name(self, policy):
        class MyCustomViewSet(PermissionedViewSet):
            name = "my_custom"
            permission_policy = policy
            required_permissions = ["access_test_management"]

        vs = MyCustomViewSet()
        assert vs.menu_item_class.__name__ == "MyCustomViewSetMenuItem"
