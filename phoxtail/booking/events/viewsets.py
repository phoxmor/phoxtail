from django.urls import path
from django.utils.translation import gettext_lazy as _
from wagtail.snippets.views.snippets import SnippetViewSet

from phoxtail.booking.core.permissions import BookingViewSet

from .admin.booking.views import (
    ReservationCreateSearchSubscriptionView,
    ReservationCreateSearchUserView,
    ReservationMoveSearchTargetEventView,
    admin_booking_event_update_form_view,
    admin_booking_filters_form_view,
    admin_booking_filters_view,
    admin_event_detail_form_view,
    admin_event_list_view,
    admin_event_reservation_create_form_view,
    admin_event_reservation_create_view,
    admin_event_reservation_move_form_view,
    admin_event_reservation_move_view,
    admin_event_reservation_update_form_view,
)
from .admin.scheduling.views import (
    admin_event_schedule_view,
    admin_schedule_actions_form_view,
    admin_schedule_actions_view,
    admin_schedule_bulk_update_status_form_view,
    admin_schedule_event_capacity_form_field_view,
    admin_schedule_event_create_form_view,
    admin_schedule_event_delete_view,
    admin_schedule_event_frequency_form_field_view,
    admin_schedule_event_update_form_view,
    admin_schedule_event_weekdays_form_field_view,
    admin_schedule_filters_form_view,
    admin_schedule_filters_view,
    admin_schedule_template_event_update_form_view,
)
from .models import Event, EventGenerationSchedule, EventGenerationScheduleExclusion


class BookingManagementViewSet(BookingViewSet):
    name = "booking_management"
    menu_label = _("Booking")
    icon = "calendar-month"
    menu_order = 100
    required_permissions = ["access_booking_management"]

    def get_urlpatterns(self):
        return [
            path("", admin_event_list_view, name="index"),
            path(
                "admin-event-detail-form/<uuid:event_id>/",
                admin_event_detail_form_view,
                name="admin_event_detail_form",
            ),
            path(
                "admin-booking-event-update-form/<uuid:event_id>/",
                admin_booking_event_update_form_view,
                name="admin_booking_event_update_form",
            ),
            path(
                "admin-event-reservation-update-form/<uuid:reservation_id>/",
                admin_event_reservation_update_form_view,
                name="admin_event_reservation_update_form",
            ),
            path(
                "admin-event-reservation-move-form/<uuid:reservation_id>/",
                admin_event_reservation_move_form_view,
                name="admin_event_reservation_move_form",
            ),
            path(
                "admin-event-reservation-move-action/<uuid:reservation_id>/",
                admin_event_reservation_move_view,
                name="admin_event_reservation_move",
            ),
            path(
                "admin-reservation-move-search-target-event/<uuid:reservation_id>/",
                ReservationMoveSearchTargetEventView.as_view(),
                name="admin_reservation_move_search_target_event",
            ),
            path(
                "admin-event-reservation-create-form/<uuid:event_id>/",
                admin_event_reservation_create_form_view,
                name="admin_event_reservation_create_form",
            ),
            path(
                "admin-event-reservation-create-action/<uuid:event_id>/",
                admin_event_reservation_create_view,
                name="admin_event_reservation_create",
            ),
            path(
                "admin-reservation-create-search-user/<uuid:event_id>/",
                ReservationCreateSearchUserView.as_view(),
                name="admin_reservation_create_search_user",
            ),
            path(
                "admin-reservation-create-search-subscription/<uuid:event_id>/",
                ReservationCreateSearchSubscriptionView.as_view(),
                name="admin_reservation_create_search_subscription",
            ),
            path(
                "admin-booking-filters-form/",
                admin_booking_filters_form_view,
                name="filters_form",
            ),
            path(
                "admin-booking-filters/",
                admin_booking_filters_view,
                name="filters",
            ),
        ]


class SchedulingManagementViewSet(BookingViewSet):
    name = "scheduling_management"
    menu_label = _("Scheduling")
    icon = "calendar-clock"
    menu_order = 100
    required_permissions = ["access_scheduling_management"]

    def get_urlpatterns(self):
        return [
            path("", admin_event_schedule_view, name="index"),
            path(
                "admin-schedule-event-create-form/",
                admin_schedule_event_create_form_view,
                name="admin_schedule_event_create_form",
            ),
            path(
                "admin-schedule-event-update-form/<uuid:event_id>/",
                admin_schedule_event_update_form_view,
                name="admin_schedule_event_update_form",
            ),
            path(
                "admin-schedule-event-delete/<uuid:event_id>/",
                admin_schedule_event_delete_view,
                name="admin_schedule_event_delete",
            ),
            path(
                "admin-schedule-template-event-update-form/<uuid:event_id>/",
                admin_schedule_template_event_update_form_view,
                name="admin_schedule_template_event_update_form",
            ),
            path(
                "admin-schedule-event-capacity-form-field/",
                admin_schedule_event_capacity_form_field_view,
                name="admin_schedule_event_capacity_form_field",
            ),
            path(
                "admin-schedule-event-frequency-form-field/",
                admin_schedule_event_frequency_form_field_view,
                name="admin_schedule_event_frequency_form_field",
            ),
            path(
                "admin-schedule-event-weekdays-form-field/",
                admin_schedule_event_weekdays_form_field_view,
                name="admin_schedule_event_weekdays_form_field",
            ),
            path(
                "admin-schedule-filters-form/",
                admin_schedule_filters_form_view,
                name="filters_form",
            ),
            path(
                "admin-schedule-filters/",
                admin_schedule_filters_view,
                name="filters",
            ),
            path(
                "admin-schedule-actions-form/",
                admin_schedule_actions_form_view,
                name="actions_form",
            ),
            path(
                "admin-schedule-actions/",
                admin_schedule_actions_view,
                name="actions",
            ),
            path(
                "admin-schedule-bulk-update-status-form/",
                admin_schedule_bulk_update_status_form_view,
                name="bulk_update_status_form",
            ),
        ]


class EventViewSet(SnippetViewSet):
    model = Event
    icon = "event"
    menu_label = _("Events")
    menu_name = _("Events")
    menu_order = 400
    list_display = [
        "service__name",
        "start_datetime",
        "end_datetime",
        "space",
        "capacity",
        "is_recurrence_template",
    ]
    list_filter = {
        "service": ["exact"],
        "service__name": ["icontains"],
        "space": ["exact"],
        "space__name": ["icontains"],
        "staff": ["exact"],
        "group": ["exact"],
        "start_datetime": ["exact", "lt", "gt"],
        "end_datetime": ["exact", "lt", "gt"],
        "status": ["exact"],
        "capacity": ["exact", "lt", "gt"],
        "notes": ["icontains"],
    }
    list_per_page = 25
    ordering = ["-start_datetime"]  # Show newest events first


class EventGenerationScheduleExclusionViewSet(SnippetViewSet):
    model = EventGenerationScheduleExclusion
    icon = "calendar-lock"
    menu_label = _("Exclusions")
    menu_name = _("Exclusions")
    menu_order = 402
    list_display = [
        "name",
        "schedule",
    ]
    list_filter = {
        "schedule": ["exact"],
        "schedule__location": ["exact"],
        "name": ["icontains"],
    }
    list_per_page = 25
    ordering = ["schedule__location__name", "name"]


class EventGenerationScheduleViewSet(SnippetViewSet):
    model = EventGenerationSchedule
    icon = "schedule"
    menu_label = _("Schedules")
    menu_name = _("Schedules")
    menu_order = 401
    list_display = [
        "location",
        "days_ahead",
        "start_time",
        "is_enabled",
    ]
    list_filter = {
        "location": ["exact"],
        "location__name": ["icontains"],
        "days_ahead": ["exact", "lt", "gt"],
        "is_enabled": ["exact"],
    }
    list_per_page = 25
    ordering = ["location__name"]
