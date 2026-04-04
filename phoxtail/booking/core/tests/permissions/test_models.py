"""
Tests for BookingAdminPermission — the permission model that defines
all booking admin permission codenames.

Verifies that the expected permissions exist in the database after
migration and that the model's Meta configuration is correct.
"""

import pytest
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType

from phoxtail.booking.core.permissions import BookingAdminPermission

pytestmark = pytest.mark.django_db

EXPECTED_CODENAMES = [
    "access_booking_management",
    "manage_reservations",
    "manage_booking_event_details",
    "access_scheduling_management",
    "create_scheduled_events",
    "edit_scheduled_events",
    "delete_scheduled_events",
    "bulk_update_scheduled_events",
    "access_billing_management",
    "manage_billing_subscriptions",
    "access_users_management",
    "create_booking_users",
    "edit_booking_users",
    "access_booking_settings",
]


class TestPermissionModel:
    """Tests for BookingAdminPermission model configuration."""

    def test_no_default_permissions(self):
        assert BookingAdminPermission._meta.default_permissions == ()

    def test_correct_number_of_permissions_defined(self):
        assert len(BookingAdminPermission._meta.permissions) == 14


class TestPermissionsExistInDatabase:
    """Tests that all expected permissions are created by migration."""

    def _get_booking_permissions(self):
        ct = ContentType.objects.get_for_model(BookingAdminPermission)
        return Permission.objects.filter(content_type=ct)

    def test_all_expected_permissions_exist(self):
        perms = self._get_booking_permissions()
        codenames = set(perms.values_list("codename", flat=True))
        for expected in EXPECTED_CODENAMES:
            assert expected in codenames, f"Missing permission: {expected}"

    def test_no_unexpected_permissions_exist(self):
        perms = self._get_booking_permissions()
        codenames = set(perms.values_list("codename", flat=True))
        assert codenames == set(EXPECTED_CODENAMES)

    def test_no_auto_generated_crud_permissions(self):
        perms = self._get_booking_permissions()
        codenames = set(perms.values_list("codename", flat=True))
        # Auto-generated Django CRUD permissions target the model name
        # (e.g. add_bookingadminpermission). Our custom permissions like
        # delete_scheduled_events should not be flagged.
        auto_crud_suffixes = (f"_{BookingAdminPermission._meta.model_name}",)
        for prefix in ("add_", "change_", "delete_", "view_"):
            matching = [
                c
                for c in codenames
                if c.startswith(prefix) and c.endswith(auto_crud_suffixes)
            ]
            assert matching == [], f"Unexpected auto-permission: {matching}"

    def test_permissions_have_content_type_booking_core(self):
        ct = ContentType.objects.get_for_model(BookingAdminPermission)
        assert ct.app_label == "phoxtail_booking_core"
        assert ct.model == "bookingadminpermission"
