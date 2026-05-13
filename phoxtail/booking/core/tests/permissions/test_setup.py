"""
Tests for booking/core/permissions/setup.py — the booking-specific wiring layer.

Verifies that the pre-configured policy, decorator, mixin, and viewset are
correctly wired to BookingAdminPermission.
"""

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.views import View

from phoxtail.booking.core.permissions import (
    BookingAdminPermission,
    BookingPermissionMixin,
    BookingViewSet,
    booking_permission_policy,
    booking_permission_required,
)
from phoxtail.core.permissions import (
    AppPermissionPolicy,
    PermissionedViewSet,
    PermissionMixin,
)

pytestmark = pytest.mark.django_db

User = get_user_model()


@pytest.fixture
def user():
    return User.objects.create_user(username="testuser", email="test@example.com", password="testpass123")


def _grant(user, *codenames):
    ct = ContentType.objects.get_for_model(BookingAdminPermission)
    perms = Permission.objects.filter(content_type=ct, codename__in=codenames)
    user.user_permissions.add(*perms)
    return User.objects.get(pk=user.pk)


class TestBookingPermissionPolicy:
    """Tests that booking_permission_policy is correctly configured."""

    def test_is_app_permission_policy_instance(self):
        assert isinstance(booking_permission_policy, AppPermissionPolicy)

    def test_uses_booking_core_app_label(self):
        assert booking_permission_policy._app_label == "phoxtail_booking_core"

    def test_resolves_permission_string_correctly(self):
        assert (
            booking_permission_policy._full_perm("access_booking_management")
            == "phoxtail_booking_core.access_booking_management"
        )


class TestBookingPermissionRequired:
    """Tests that booking_permission_required decorator works with booking policy."""

    def _dummy_view(self, request):
        return HttpResponse("ok")

    def test_allows_with_booking_permission(self, user, rf):
        user = _grant(user, "access_booking_management")
        view = booking_permission_required("access_booking_management")(self._dummy_view)
        request = rf.get("/")
        request.user = user
        response = view(request)
        assert response.status_code == 200

    def test_denies_without_booking_permission(self, user, rf):
        view = booking_permission_required("access_booking_management")(self._dummy_view)
        request = rf.get("/")
        request.user = user
        with pytest.raises(PermissionDenied):
            view(request)


class TestBookingPermissionMixin:
    """Tests that BookingPermissionMixin is pre-wired with booking policy."""

    def test_inherits_permission_mixin(self):
        assert issubclass(BookingPermissionMixin, PermissionMixin)

    def test_has_booking_policy_pre_wired(self):
        assert BookingPermissionMixin.permission_policy is booking_permission_policy

    def test_subclass_only_needs_required_permissions(self, user, rf):
        class TestView(BookingPermissionMixin, View):
            required_permissions = ["access_booking_management"]

            def get(self, request):
                return HttpResponse("ok")

        user = _grant(user, "access_booking_management")
        request = rf.get("/")
        request.user = user
        response = TestView.as_view()(request)
        assert response.status_code == 200

    def test_subclass_denied_without_permission(self, user, rf):
        class TestView(BookingPermissionMixin, View):
            required_permissions = ["access_booking_management"]

            def get(self, request):
                return HttpResponse("ok")

        request = rf.get("/")
        request.user = user
        with pytest.raises(PermissionDenied):
            TestView.as_view()(request)


class TestBookingViewSet:
    """Tests that BookingViewSet is pre-wired with booking policy."""

    def test_inherits_permissioned_viewset(self):
        assert issubclass(BookingViewSet, PermissionedViewSet)

    def test_has_booking_policy_pre_wired(self):
        assert BookingViewSet.permission_policy is booking_permission_policy

    def test_subclass_menu_respects_permissions(self, user, rf):
        class TestViewSet(BookingViewSet):
            name = "test"
            required_permissions = ["access_booking_management"]

        vs = TestViewSet()
        menu_item = vs.menu_item_class("Test", "/test/")
        request = rf.get("/")
        request.user = user
        assert menu_item.is_shown(request) is False

    def test_subclass_menu_shown_with_permission(self, user, rf):
        user = _grant(user, "access_booking_management")

        class TestViewSet(BookingViewSet):
            name = "test"
            required_permissions = ["access_booking_management"]

        vs = TestViewSet()
        menu_item = vs.menu_item_class("Test", "/test/")
        request = rf.get("/")
        request.user = user
        assert menu_item.is_shown(request) is True
