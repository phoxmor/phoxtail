from django.urls import path

from . import views

app_name = "events"

urlpatterns = [
    # Main list to view all available events
    path("", views.event_list_view, name="list"),
    # Filters
    path(
        "booking-filters-form/",
        views.booking_filters_form_view,
        name="filters_form",
    ),
    path(
        "booking-filters/",
        views.booking_filters_view,
        name="filters",
    ),
    # Reservation forms and actions
    path(
        "event-reservation-create-form/",
        views.event_reservation_create_form_view,
        name="event_reservation_create_form",
    ),
    path(
        "event-reservation-create/",
        views.event_reservation_create_view,
        name="event_reservation_create",
    ),
    path(
        "event-waitlisted-reservation-create-form/",
        views.event_waitlisted_reservation_create_form_view,
        name="event_waitlisted_reservation_create_form",
    ),
    path(
        "event-waitlisted-reservation-create/",
        views.event_waitlisted_reservation_create_view,
        name="event_waitlisted_reservation_create",
    ),
    path(
        "event-waitlisted-reservation-cancel-form/<uuid:reservation_id>/",
        views.event_waitlisted_reservation_cancel_form_view,
        name="event_waitlisted_reservation_cancel_form",
    ),
    path(
        "event-waitlisted-reservation-cancel/<uuid:reservation_id>/",
        views.event_waitlisted_reservation_cancel_view,
        name="event_waitlisted_reservation_cancel",
    ),
    path(
        "event-waitlisted-reservation-confirm-form/<uuid:reservation_id>/",
        views.event_waitlisted_reservation_confirm_form_view,
        name="event_waitlisted_reservation_confirm_form",
    ),
    path(
        "event-waitlisted-reservation-confirm/<uuid:reservation_id>/",
        views.event_waitlisted_reservation_confirm_view,
        name="event_waitlisted_reservation_confirm",
    ),
    path(
        "event-reservation-cancel-form/<uuid:reservation_id>/",
        views.event_reservation_cancel_form_view,
        name="event_reservation_cancel_form",
    ),
    path(
        "event-reservation-cancel/<uuid:reservation_id>/",
        views.event_reservation_cancel_view,
        name="event_reservation_cancel",
    ),
]
