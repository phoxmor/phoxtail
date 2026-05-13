from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse

from phoxtail.booking.core.permissions import (
    booking_permission_policy,
    booking_permission_required,
)
from phoxtail.booking.events.models import Event
from phoxtail.booking.reservations.models import Reservation
from phoxtail.booking.reservations.services import ReservationService
from phoxtail.core.views import SingleSelectSearchView

from ..utils import BookingContextBuilder
from .forms import ReservationCreateForm, ReservationMoveForm


@booking_permission_required("access_booking_management")
def admin_event_list_view(request):
    context = BookingContextBuilder.get_full_context(request)

    is_htmx_request = bool(request.htmx)
    context["is_htmx_request"] = is_htmx_request

    if is_htmx_request:
        return render(
            request,
            "phoxtail_booking_events/admin/booking/partials/calendar.html",
            context,
        )

    return render(request, "phoxtail_booking_events/admin/booking/index.html", context)


@booking_permission_required("access_booking_management")
def admin_event_detail_form_view(request, event_id):
    """
    Displays event information and reservations for admin review.
    """
    event = get_object_or_404(Event, uuid=event_id)

    reservations = event.reservations.select_related(
        "user", "subscription", "subscription__subscription_type"
    ).with_status_order()

    context = {
        "event": event,
        "reservations": reservations,
    }

    return render(
        request,
        "phoxtail_booking_events/admin/booking/partials/forms/detail/admin_event_detail_form.html",
        context,
    )


@booking_permission_required("access_booking_management", "manage_reservations")
def admin_event_reservation_update_form_view(request, reservation_id):
    """
    Displays and processes the edit reservation form for admin.
    Handles both GET (display form) and POST (process status transition).
    """
    from phoxtail.booking.reservations.forms import ReservationUpdateForm

    reservation = get_object_or_404(
        Reservation.objects.select_related(
            "user",
            "event",
            "event__service",
            "event__space",
            "event__space__location",
            "subscription",
            "subscription__subscription_type",
        ),
        uuid=reservation_id,
    )

    if request.method == "POST":
        form = ReservationUpdateForm(request.POST, instance=reservation)
        if form.is_valid():
            try:
                form.save(user=request.user)
                if form.reservation_deleted:
                    messages.success(
                        request,
                        f"Reservation for {reservation.user.get_full_name() or reservation.user.username} "
                        f"has been cancelled and deleted (within cancellation period).",
                    )
                else:
                    messages.success(
                        request,
                        f"Reservation for {reservation.user.get_full_name() or reservation.user.username} "
                        f"updated successfully.",
                    )
            except ValidationError as e:
                for message in e.messages:
                    messages.error(request, message)
        else:
            for errors in form.errors.values():
                for error in errors:
                    messages.error(request, error)

        calendar_context = BookingContextBuilder.get_full_context(request)
        event = reservation.event
        reservations = event.reservations.select_related(
            "user", "subscription", "subscription__subscription_type"
        ).with_status_order()

        context = {
            "form": form,
            "reservation": reservation,
            "reservation_deleted": form.reservation_deleted,
            "event": event,
            "reservations": reservations,
            **calendar_context,
        }

        return render(
            request,
            "phoxtail_booking_events/admin/booking/partials/forms/update/reservation/form_response.html",
            context,
        )
    else:
        form = ReservationUpdateForm(instance=reservation)

    context = {
        "form": form,
        "reservation": reservation,
    }

    return render(
        request,
        "phoxtail_booking_events/admin/booking/partials/forms/update/reservation/form.html",
        context,
    )


@booking_permission_required("access_booking_management", "manage_reservations")
def admin_event_reservation_move_form_view(request, reservation_id):
    """
    Displays the move reservation drawer form for admin.
    """
    reservation = get_object_or_404(
        Reservation.objects.select_related(
            "user",
            "event",
            "event__service",
            "event__space",
            "event__space__location",
            "subscription",
            "subscription__subscription_type",
        ),
        uuid=reservation_id,
    )
    form = ReservationMoveForm(reservation=reservation)

    context = {
        "reservation": reservation,
        "form": form,
        "search_target_event_url": reverse(
            "booking_management:admin_reservation_move_search_target_event",
            kwargs={"reservation_id": reservation.uuid},
        ),
    }

    return render(
        request,
        "phoxtail_booking_events/admin/booking/partials/forms/move/admin_event_reservation_move_form.html",
        context,
    )


@booking_permission_required("access_booking_management", "manage_reservations")
def admin_event_reservation_move_view(request, reservation_id):
    """
    Processes the reservation move action.
    """
    if request.method != "POST":
        return HttpResponse("Method not allowed", status=405)

    reservation = get_object_or_404(
        Reservation.objects.select_related("event"),
        uuid=reservation_id,
    )
    form = ReservationMoveForm(request.POST, reservation=reservation)

    calendar_context = BookingContextBuilder.get_full_context(request)
    original_event = reservation.event
    reservations = original_event.reservations.select_related(
        "user", "subscription", "subscription__subscription_type"
    ).with_status_order()

    context = {
        **calendar_context,
        "original_event": original_event,
        "reservations": reservations,
        "reservation": reservation,
        "form": form,
        "search_target_event_url": reverse(
            "booking_management:admin_reservation_move_search_target_event",
            kwargs={"reservation_id": reservation.uuid},
        ),
    }

    moved = False

    if form.is_valid():
        try:
            updated_reservation = ReservationService(reservation).admin.move(
                target_event_id=str(form.cleaned_data["target_event"].uuid),
            )
            moved = True
            messages.success(
                request,
                f"Reservation successfully moved to {updated_reservation.event.service.name} "
                f"on {updated_reservation.event.start_datetime.strftime('%B %d, %Y at %I:%M %p')}.",
            )
            calendar_context = BookingContextBuilder.get_full_context(request)
            context.update(calendar_context)
        except ValidationError as e:
            for message in e.messages:
                messages.error(request, message)

    context["moved"] = moved

    return render(
        request,
        "phoxtail_booking_events/admin/booking/partials/forms/move/admin_event_reservation_move_response.html",
        context,
    )


def _reservation_move_form_state_context(form):
    """Shared helper: form state values for OOB placeholder sync."""
    return {
        "target_event_value": form["target_event"].value(),
    }


class ReservationMoveSearchTargetEventView(SingleSelectSearchView):
    """Search CBV for target event in move reservation flow."""

    permission_policy = booking_permission_policy
    required_permissions = ["access_booking_management", "manage_reservations"]
    form_class = ReservationMoveForm
    field_name = "target_event"
    search_url_name = "booking_management:admin_reservation_move_search_target_event"
    hx_include = "#move-reservation-parent-fields, #move-reservation-form-placeholder"
    item_template = "phoxtail_booking_events/admin/booking/partials/forms/move/widgets/event_item_display.html"
    oob_response_template = (
        "phoxtail_booking_events/admin/booking/partials/forms/move/widgets/target_event_search_response.html"
    )

    def get_form(self, data):
        reservation = get_object_or_404(
            Reservation.objects.select_related("event"),
            uuid=self.kwargs["reservation_id"],
        )
        return self.form_class(data, reservation=reservation)

    def get_search_url(self):
        return reverse(
            self.search_url_name,
            kwargs={"reservation_id": self.kwargs["reservation_id"]},
        )

    def get_extra_context(self, form):
        return _reservation_move_form_state_context(form)


@booking_permission_required("access_booking_management", "manage_reservations")
def admin_event_reservation_create_form_view(request, event_id):
    """
    Displays the create reservation drawer form for admin.
    """
    event = get_object_or_404(Event, uuid=event_id)
    form = ReservationCreateForm(event=event)

    context = {
        "event": event,
        "form": form,
        "search_user_url": reverse(
            "booking_management:admin_reservation_create_search_user",
            kwargs={"event_id": event.uuid},
        ),
        "search_subscription_url": reverse(
            "booking_management:admin_reservation_create_search_subscription",
            kwargs={"event_id": event.uuid},
        ),
    }

    return render(
        request,
        "phoxtail_booking_events/admin/booking/partials/forms/create/admin_event_reservation_create_form.html",
        context,
    )


@booking_permission_required("access_booking_management", "manage_reservations")
def admin_event_reservation_create_view(request, event_id):
    """
    Processes the reservation creation action for admin.
    """
    if request.method != "POST":
        return HttpResponse("Method not allowed", status=405)

    event = get_object_or_404(Event, uuid=event_id)
    form = ReservationCreateForm(request.POST, event=event)

    calendar_context = BookingContextBuilder.get_full_context(request)
    reservations = event.reservations.select_related(
        "user", "subscription", "subscription__subscription_type"
    ).with_status_order()

    context = {
        **calendar_context,
        "event": event,
        "reservations": reservations,
        "form": form,
        "search_user_url": reverse(
            "booking_management:admin_reservation_create_search_user",
            kwargs={"event_id": event.uuid},
        ),
        "search_subscription_url": reverse(
            "booking_management:admin_reservation_create_search_subscription",
            kwargs={"event_id": event.uuid},
        ),
    }

    created = False

    if form.is_valid():
        try:
            new_reservation = ReservationService().admin.create(
                user_id=str(form.cleaned_data["user"].pk),
                event_id=str(event.uuid),
                subscription_id=str(form.cleaned_data["subscription"].uuid),
                status=form.cleaned_data["status"],
            )
            created = True
            messages.success(
                request,
                f"{new_reservation.status} reservation successfully created for "
                f"{new_reservation.user.get_full_name() or new_reservation.user.username} "
                f"in {new_reservation.event.service.name} on "
                f"{new_reservation.event.start_datetime.strftime('%B %d, %Y at %I:%M %p')}.",
            )
            calendar_context = BookingContextBuilder.get_full_context(request)
            context.update(calendar_context)
        except ValidationError as e:
            for message in e.messages:
                messages.error(request, message)

    context["created"] = created

    return render(
        request,
        "phoxtail_booking_events/admin/booking/partials/forms/create/admin_event_reservation_create_response.html",
        context,
    )


def _reservation_create_form_state_context(form):
    """Shared helper: form state values for OOB placeholder sync."""
    return {
        "user_value": form["user"].value(),
        "subscription_value": form["subscription"].value(),
        "status_value": form["status"].value(),
    }


class _ReservationCreateSingleSelectBase(SingleSelectSearchView):
    """Shared base for reservation create search views."""

    permission_policy = booking_permission_policy
    required_permissions = ["access_booking_management", "manage_reservations"]
    form_class = ReservationCreateForm
    hx_include = "#create-reservation-parent-fields, #create-reservation-form-placeholder"

    def get_form(self, data):
        event = get_object_or_404(Event, uuid=self.kwargs["event_id"])
        return self.form_class(data, event=event)

    def get_search_url(self):
        return reverse(
            self.search_url_name,
            kwargs={"event_id": self.kwargs["event_id"]},
        )

    def get_extra_context(self, form):
        event = get_object_or_404(Event, uuid=self.kwargs["event_id"])
        return {
            **_reservation_create_form_state_context(form),
            "event": event,
        }


class ReservationCreateSearchUserView(_ReservationCreateSingleSelectBase):
    field_name = "user"
    search_url_name = "booking_management:admin_reservation_create_search_user"
    oob_response_template = (
        "phoxtail_booking_events/admin/booking/partials/forms/create/widgets/user_search_response.html"
    )
    item_template = "phoxtail_booking_events/admin/booking/partials/forms/create/widgets/user_item_display.html"

    def get_extra_context(self, form):
        context = super().get_extra_context(form)
        event = context["event"]
        context.update(
            {
                "subscription_field": form["subscription"],
                "subscription_search_url": reverse(
                    "booking_management:admin_reservation_create_search_subscription",
                    kwargs={"event_id": event.uuid},
                ),
                "subscription_hx_include": self.hx_include,
            }
        )
        return context


class ReservationCreateSearchSubscriptionView(_ReservationCreateSingleSelectBase):
    field_name = "subscription"
    search_url_name = "booking_management:admin_reservation_create_search_subscription"
    oob_response_template = (
        "phoxtail_booking_events/admin/booking/partials/forms/create/widgets/subscription_search_response.html"
    )
    item_template = "phoxtail_booking_events/admin/booking/partials/forms/create/widgets/subscription_item_display.html"


@booking_permission_required("access_booking_management")
def admin_booking_filters_form_view(request):
    """
    Displays the filters modal for the booking view.
    Uses lightweight filter context only - no expensive events query.
    """

    context = BookingContextBuilder.get_filters_context(request)

    return render(
        request,
        "phoxtail_booking_events/admin/booking/partials/forms/filters/form.html",
        context,
    )


@booking_permission_required("access_booking_management")
def admin_booking_filters_view(request):
    """
    Processes filter changes and returns OOB swaps to update both the calendar and the filters form.
    This allows filter state to be managed server-side without JavaScript.
    """
    context = BookingContextBuilder.get_full_context(request)

    return render(
        request,
        "phoxtail_booking_events/admin/booking/partials/forms/filters/form_response.html",
        context,
    )


@booking_permission_required("access_booking_management", "manage_booking_event_details")
def admin_booking_event_update_form_view(request, event_id):
    """
    Displays the update event form in the booking section for admin to edit existing events.
    Handles both GET (display form) and POST (process form) requests.
    """
    from phoxtail.booking.events.forms import EventUpdateForm

    event = get_object_or_404(Event, uuid=event_id)

    if request.method == "POST":
        form = EventUpdateForm(request.POST, instance=event)
        if form.is_valid():
            try:
                event = form.save()
                # Get the number of events updated from the form
                events_updated = getattr(form, "events_updated", 1)

                if events_updated == 1:
                    messages.success(
                        request,
                        f"Event '{event.service.name}' successfully updated"
                        f" for {event.start_datetime.strftime('%B %d, %Y at %I:%M %p')}.",
                    )
                else:
                    messages.success(
                        request,
                        f"Successfully updated {events_updated} events in the '{event.short_series_id}' series.",
                    )
            except ValidationError as e:
                for message in e.messages:
                    messages.error(request, message)
        else:
            # Form has errors, add to messages
            for errors in form.errors.values():
                for error in errors:
                    messages.error(request, error)

        calendar_context = BookingContextBuilder.get_full_context(request)

        context = {
            "form": form,
            "event": event,
            **calendar_context,
        }

        return render(
            request,
            "phoxtail_booking_events/admin/booking/partials/forms/update/event/form_response.html",
            context,
        )
    else:
        form = EventUpdateForm(instance=event)

    context = {
        "form": form,
        "event": event,
    }

    return render(
        request,
        "phoxtail_booking_events/admin/booking/partials/forms/update/event/form.html",
        context,
    )
