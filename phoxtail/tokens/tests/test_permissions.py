import pytest
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType

from phoxtail.tokens.permissions import (
    access_tokens_permission_policy,
    access_tokens_permission_required,
)
from phoxtail.tokens.permissions.models import AccessTokensAdminPermission

from .conftest import grant_token_permissions

pytestmark = pytest.mark.django_db


EXPECTED_PERMS = {
    "access_tokens_management",
    "create_access_tokens",
    "revoke_access_tokens",
    "manage_all_tokens",
}


class TestPermissionsRegistered:
    def test_all_expected_permissions_exist(self):
        ct = ContentType.objects.get_for_model(AccessTokensAdminPermission)
        codenames = set(
            Permission.objects.filter(content_type=ct).values_list(
                "codename", flat=True
            )
        )
        assert EXPECTED_PERMS.issubset(codenames)

    def test_no_default_permissions(self):
        ct = ContentType.objects.get_for_model(AccessTokensAdminPermission)
        codenames = set(
            Permission.objects.filter(content_type=ct).values_list(
                "codename", flat=True
            )
        )
        # default_permissions = () so add/change/delete/view should NOT exist.
        for forbidden in {"add_", "change_", "delete_", "view_"}:
            assert not any(
                cn.startswith(forbidden + "accesstokensadminpermission")
                for cn in codenames
            )


class TestPolicyEvaluation:
    def test_anonymous_inactive_user_has_no_perms(self, user):
        user.is_active = False
        user.save()
        assert (
            access_tokens_permission_policy.user_has_permission(
                user, "access_tokens_management"
            )
            is False
        )

    def test_user_without_grants_denied(self, user):
        for action in EXPECTED_PERMS:
            assert (
                access_tokens_permission_policy.user_has_permission(user, action)
                is False
            )

    def test_user_with_grant_allowed(self, user):
        u = grant_token_permissions(user, "access_tokens_management")
        assert (
            access_tokens_permission_policy.user_has_permission(
                u, "access_tokens_management"
            )
            is True
        )
        # Did not grant unrelated permissions.
        assert (
            access_tokens_permission_policy.user_has_permission(
                u, "manage_all_tokens"
            )
            is False
        )

    def test_superuser_short_circuits(self, superuser):
        for action in EXPECTED_PERMS:
            assert (
                access_tokens_permission_policy.user_has_permission(
                    superuser, action
                )
                is True
            )


class TestPermissionRequiredDecorator:
    def test_non_htmx_denial_raises_permission_denied(self, user):
        from django.core.exceptions import PermissionDenied
        from django.test import RequestFactory

        @access_tokens_permission_required("access_tokens_management")
        def view(request):
            return "ok"

        req = RequestFactory().get("/")
        req.user = user
        # Non-HTMX request: HtmxDetails is falsy without HX-Request header,
        # so the decorator takes the raise-PermissionDenied branch.
        req.htmx = False
        with pytest.raises(PermissionDenied):
            view(req)

    def test_htmx_denial_returns_204_with_toast_event(self, user):
        from django.test import RequestFactory

        @access_tokens_permission_required("access_tokens_management")
        def view(request):
            return "ok"

        req = RequestFactory().get("/", HTTP_HX_REQUEST="true")
        req.user = user
        response = view(req)
        # HTMX path: 204 + HX-Trigger header for toast.
        assert response.status_code == 204
        assert "HX-Trigger" in response

    def test_decorator_allows_user_with_permission(self, user):
        u = grant_token_permissions(user, "access_tokens_management")

        @access_tokens_permission_required("access_tokens_management")
        def view(request):
            return "ok"

        from django.test import RequestFactory

        req = RequestFactory().get("/")
        req.user = u
        assert view(req) == "ok"

    def test_decorator_requires_all_listed_permissions(self, user):
        from django.core.exceptions import PermissionDenied
        from django.test import RequestFactory

        @access_tokens_permission_required(
            "access_tokens_management", "manage_all_tokens"
        )
        def view(request):
            return "ok"

        # Granted only one of the two required perms.
        u = grant_token_permissions(user, "access_tokens_management")
        req = RequestFactory().get("/")
        req.user = u
        req.htmx = False
        with pytest.raises(PermissionDenied):
            view(req)
