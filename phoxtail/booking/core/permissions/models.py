from django.db import models
from django.utils.translation import gettext_lazy as _


class BookingAdminPermission(models.Model):
    """
    ContentType anchor for booking admin permissions. Never instantiated —
    exists only so Django creates Permission rows in auth_permission during
    migrate.
    """

    class Meta:
        default_permissions = ()
        permissions = [
            # ── Booking Management ──────────────────────────────
            ("access_booking_management", "Can access booking management"),
            ("manage_reservations", "Can create, edit, move reservations"),
            ("manage_booking_event_details", "Can edit event details in booking view"),
            # ── Scheduling Management ───────────────────────────
            ("access_scheduling_management", "Can access scheduling management"),
            ("create_scheduled_events", "Can create events in scheduling"),
            ("edit_scheduled_events", "Can edit events in scheduling"),
            ("delete_scheduled_events", "Can delete events in scheduling"),
            ("bulk_update_scheduled_events", "Can bulk-update event status"),
            # ── Billing Management ──────────────────────────────
            ("access_billing_management", "Can access billing management"),
            ("manage_billing_subscriptions", "Can create and edit subscriptions"),
            # ── Users Management ────────────────────────────────
            ("access_users_management", "Can access users management"),
            ("create_booking_users", "Can create users"),
            ("edit_booking_users", "Can edit users"),
            # ── Settings ────────────────────────────────────────
            ("access_booking_settings", "Can access booking settings"),
        ]

        verbose_name = _("Booking")
        verbose_name_plural = _("Booking")
