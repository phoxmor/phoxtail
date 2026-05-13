"""
Tests for AppPermissionPolicy — the generic permission policy base class.

Each test exercises a single concern: either the policy correctly grants
access, correctly denies access, or correctly handles edge cases like
inactive users and superusers.
"""

import pytest
from django.contrib.auth import get_user_model

from phoxtail.core.tests.conftest import grant_permissions

pytestmark = pytest.mark.django_db

User = get_user_model()


class TestUserHasPermission:
    """Tests for policy.user_has_permission(user, action)."""

    def test_denies_when_user_lacks_permission(self, policy, user):
        assert policy.user_has_permission(user, "access_test_management") is False

    def test_grants_when_user_has_permission(self, policy, user):
        user = grant_permissions(user, "access_test_management")
        assert policy.user_has_permission(user, "access_test_management") is True

    def test_superuser_bypasses_all_checks(self, policy, superuser):
        assert policy.user_has_permission(superuser, "access_test_management") is True
        assert policy.user_has_permission(superuser, "manage_test_items") is True

    def test_inactive_user_always_denied(self, policy, user):
        user = grant_permissions(user, "access_test_management")
        user.is_active = False
        user.save()
        user = User.objects.get(pk=user.pk)
        assert policy.user_has_permission(user, "access_test_management") is False

    def test_inactive_superuser_always_denied(self, policy, superuser):
        superuser.is_active = False
        superuser.save()
        superuser = User.objects.get(pk=superuser.pk)
        assert policy.user_has_permission(superuser, "access_test_management") is False

    def test_having_one_permission_does_not_grant_another(self, policy, user):
        user = grant_permissions(user, "access_test_management")
        assert policy.user_has_permission(user, "manage_test_items") is False


class TestUserHasAnyPermission:
    """Tests for policy.user_has_any_permission(user, actions)."""

    def test_denies_when_user_lacks_all_permissions(self, policy, user):
        assert policy.user_has_any_permission(user, ["access_test_management", "manage_test_items"]) is False

    def test_grants_when_user_has_one_of_listed_permissions(self, policy, user):
        user = grant_permissions(user, "manage_test_items")
        assert policy.user_has_any_permission(user, ["access_test_management", "manage_test_items"]) is True

    def test_grants_when_user_has_all_listed_permissions(self, policy, user):
        user = grant_permissions(user, "access_test_management", "manage_test_items")
        assert policy.user_has_any_permission(user, ["access_test_management", "manage_test_items"]) is True

    def test_superuser_bypasses_all_checks(self, policy, superuser):
        assert policy.user_has_any_permission(superuser, ["access_test_management", "manage_test_items"]) is True

    def test_inactive_user_always_denied(self, policy, user):
        user = grant_permissions(user, "access_test_management")
        user.is_active = False
        user.save()
        user = User.objects.get(pk=user.pk)
        assert policy.user_has_any_permission(user, ["access_test_management"]) is False

    def test_empty_actions_list_denies(self, policy, user):
        assert policy.user_has_any_permission(user, []) is False


class TestFullPerm:
    """Tests for the permission string construction."""

    def test_constructs_correct_permission_string(self, policy):
        assert policy._full_perm("access_test_management") == "phoxtail_core_testapp.access_test_management"

    def test_app_label_comes_from_model_meta(self):
        from phoxtail.core.permissions import AppPermissionPolicy
        from phoxtail.core.tests.testapp.models import TestAdminPermission

        policy = AppPermissionPolicy(TestAdminPermission)
        assert policy._app_label == "phoxtail_core_testapp"
