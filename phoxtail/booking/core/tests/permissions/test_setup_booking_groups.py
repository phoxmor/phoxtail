"""
Tests for the setup_booking_groups management command.

Each test exercises a single concern: groups are created with the correct
permissions, and the command is idempotent.
"""

import pytest
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command

from phoxtail.booking.core.management.commands.setup_booking_groups import (
    CONFIG_MODELS,
    OPERATIONAL_MODELS,
    SNIPPET_APP_LABELS,
    STAFF_CONFIG_MODELS,
    STAFF_OPERATIONAL_MODELS,
)
from phoxtail.booking.core.permissions import BookingAdminPermission

pytestmark = pytest.mark.django_db


def _get_custom_permissions():
    ct = ContentType.objects.get_for_model(BookingAdminPermission)
    return Permission.objects.filter(content_type=ct)


def _get_snippet_permissions(models, actions=None):
    qs = Permission.objects.filter(
        content_type__app_label__in=SNIPPET_APP_LABELS,
        content_type__model__in=models,
    )
    if actions:
        qs = qs.filter(codename__regex=r"^(%s)" % "|".join(f"{a}_" for a in actions))
    return set(qs.values_list("codename", flat=True))


def _get_all_booking_permissions():
    """All permissions assigned to Booking Admin (custom + all snippet)."""
    custom = set(_get_custom_permissions().values_list("codename", flat=True))
    snippet = _get_snippet_permissions(CONFIG_MODELS + OPERATIONAL_MODELS)
    return custom | snippet


def _group_codenames(group_name):
    group = Group.objects.get(name=group_name)
    return set(group.permissions.values_list("codename", flat=True))


class TestSetupBookingGroups:
    """Tests for the setup_booking_groups management command."""

    def test_creates_four_groups(self):
        call_command("setup_booking_groups")
        assert (
            Group.objects.filter(
                name__in=[
                    "Booking Admin",
                    "Booking Manager",
                    "Booking Staff",
                    "Booking Viewer",
                ]
            ).count()
            == 4
        )

    def test_booking_admin_has_all_permissions(self):
        call_command("setup_booking_groups")
        assert _group_codenames("Booking Admin") == _get_all_booking_permissions()

    def test_booking_manager_excludes_settings(self):
        call_command("setup_booking_groups")
        codenames = _group_codenames("Booking Manager")
        assert "access_booking_settings" not in codenames
        custom = set(
            _get_custom_permissions().exclude(codename="access_booking_settings").values_list("codename", flat=True)
        )
        snippet = _get_snippet_permissions(OPERATIONAL_MODELS) | _get_snippet_permissions(
            CONFIG_MODELS, actions=["view"]
        )
        assert codenames == custom | snippet

    def test_booking_staff_has_correct_permissions(self):
        call_command("setup_booking_groups")
        expected_custom = {
            "access_booking_management",
            "manage_reservations",
            "access_scheduling_management",
        }
        expected_snippet = _get_snippet_permissions(STAFF_CONFIG_MODELS, actions=["view"]) | _get_snippet_permissions(
            STAFF_OPERATIONAL_MODELS, actions=["view", "change"]
        )
        assert _group_codenames("Booking Staff") == expected_custom | expected_snippet

    def test_booking_viewer_has_only_access_and_view_permissions(self):
        call_command("setup_booking_groups")
        codenames = _group_codenames("Booking Viewer")
        custom_codenames = set(_get_custom_permissions().values_list("codename", flat=True))
        for codename in codenames:
            if codename in custom_codenames:
                assert codename.startswith("access_"), f"Unexpected non-access custom permission: {codename}"
            else:
                assert codename.startswith("view_"), f"Unexpected non-view snippet permission: {codename}"
        expected_custom = {
            "access_booking_management",
            "access_scheduling_management",
            "access_billing_management",
            "access_users_management",
            "access_booking_settings",
        }
        expected_snippet = _get_snippet_permissions(CONFIG_MODELS + OPERATIONAL_MODELS, actions=["view"])
        assert codenames == expected_custom | expected_snippet


class TestIdempotency:
    """Tests that the command is safe to run multiple times."""

    def test_running_twice_does_not_duplicate_groups(self):
        call_command("setup_booking_groups")
        call_command("setup_booking_groups")
        assert Group.objects.filter(name="Booking Admin").count() == 1

    def test_running_twice_preserves_permissions(self):
        call_command("setup_booking_groups")
        first_run = _group_codenames("Booking Admin")
        call_command("setup_booking_groups")
        second_run = _group_codenames("Booking Admin")
        assert first_run == second_run

    def test_updates_permissions_on_rerun(self):
        call_command("setup_booking_groups")
        # Manually remove a permission from a group
        group = Group.objects.get(name="Booking Admin")
        perm = group.permissions.first()
        group.permissions.remove(perm)
        assert group.permissions.count() < len(_get_all_booking_permissions())
        # Re-running restores it
        call_command("setup_booking_groups")
        assert _group_codenames("Booking Admin") == _get_all_booking_permissions()
