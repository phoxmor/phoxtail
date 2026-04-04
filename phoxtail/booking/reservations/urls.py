from django.urls import path

from . import views

app_name = "reservations"

urlpatterns = [
    # Main list to view all available reservations
    path("", views.reservation_list_view, name="list"),
    path(
        "reservation-cancel-form/<uuid:reservation_id>/",
        views.reservation_cancel_form_view,
        name="reservation_cancel_form",
    ),
    path(
        "reservation-cancel/<uuid:reservation_id>/",
        views.reservation_cancel_view,
        name="reservation_cancel",
    ),
    path(
        "waitlisted-reservation-cancel-form/<uuid:reservation_id>/",
        views.waitlisted_reservation_cancel_form_view,
        name="waitlisted_reservation_cancel_form",
    ),
    path(
        "waitlisted-reservation-cancel/<uuid:reservation_id>/",
        views.waitlisted_reservation_cancel_view,
        name="waitlisted_reservation_cancel",
    ),
    path(
        "waitlisted-reservation-confirm-form/<uuid:reservation_id>/",
        views.waitlisted_reservation_confirm_form_view,
        name="waitlisted_reservation_confirm_form",
    ),
    path(
        "waitlisted-reservation-confirm/<uuid:reservation_id>/",
        views.waitlisted_reservation_confirm_view,
        name="waitlisted_reservation_confirm",
    ),
]
