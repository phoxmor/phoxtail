from django.shortcuts import render
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from phoxtail.booking.core.permissions import booking_permission_required


@booking_permission_required("access_booking_settings")
def admin_settings_index_view(request):
    settings_items = [
        {
            "label": _("Locations"),
            "icon": "site",
            "description": _("Manage venue locations and their details."),
            "url": reverse("wagtailsnippets_phoxtail_booking_core_location:list"),
        },
        {
            "label": _("Users"),
            "icon": "groups",
            "description": _("Manage user accounts, permissions, and profiles."),
            "url": reverse("users_management:index"),
        },
        {
            "label": _("Staff"),
            "icon": "groups-2",
            "description": _("Manage staff members and their assignments."),
            "url": reverse("wagtailsnippets_phoxtail_booking_core_staff:list"),
        },
        {
            "label": _("Services"),
            "icon": "view-apps",
            "description": _("Configure the services offered at your locations."),
            "url": reverse("wagtailsnippets_phoxtail_booking_services_service:list"),
        },
        {
            "label": _("Subscription Types"),
            "icon": "doc-full",
            "description": _("Define subscription plans, pricing, and durations."),
            "url": reverse(
                "wagtailsnippets_phoxtail_booking_subscriptions_subscriptiontype:list"
            ),
        },
        {
            "label": _("Subscriptions"),
            "icon": "payment-card",
            "description": _("View and manage member subscriptions."),
            "url": reverse(
                "wagtailsnippets_phoxtail_booking_subscriptions_subscription:list"
            ),
        },
        {
            "label": _("Events"),
            "icon": "event",
            "description": _("Browse and manage individual event records."),
            "url": reverse("wagtailsnippets_phoxtail_booking_events_event:list"),
        },
        {
            "label": _("Schedules"),
            "icon": "schedule",
            "description": _("Configure automatic event generation schedules."),
            "url": reverse(
                "wagtailsnippets_phoxtail_booking_events_eventgenerationschedule:list"
            ),
        },
        {
            "label": _("Schedule Exclusions"),
            "icon": "calendar-lock",
            "description": _(
                "Define date periods when events should not be generated (e.g. holidays, closures)."
            ),
            "url": reverse(
                "wagtailsnippets_phoxtail_booking_events_eventgenerationscheduleexclusion:list"
            ),
        },
        {
            "label": _("Reservations"),
            "icon": "event-available",
            "description": _("View and manage all reservations."),
            "url": reverse(
                "wagtailsnippets_phoxtail_booking_reservations_reservation:list"
            ),
        },
        {
            "label": _("Groups"),
            "icon": "lock",
            "description": _(
                "Manage booking groups and control access to restricted events."
            ),
            "url": reverse("wagtailsnippets_phoxtail_booking_core_bookinggroup:list"),
        },
    ]
    return render(
        request,
        "phoxtail_booking_core/admin/settings/index.html",
        {"settings_items": settings_items},
    )
