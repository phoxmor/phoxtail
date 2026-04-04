from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render

from .constants import ReservationStatus
from .models import Reservation
from .services import ReservationService
from .utils import get_reservation_list_context


@login_required
def reservation_list_view(request):
    """
    Displays a list of all available reservations for the logged-in user.
    """

    context = get_reservation_list_context(request.user)
    return render(request, "phoxtail_booking_reservations/list/index.html", context)


@login_required
def reservation_cancel_form_view(request, reservation_id):
    """
    Displays reservation details in a modal when clicking a confirmed reservation from the list.
    Returns only the reservation content without dashboard layout for modal display.
    """
    reservation = get_object_or_404(Reservation, uuid=reservation_id, user=request.user)
    context = {
        "reservation": reservation,
    }
    return render(
        request,
        "phoxtail_booking_reservations/list/partials/forms/reservation_cancel_form.html",
        context,
    )


@login_required
def reservation_cancel_view(request, reservation_id):
    """
    Cancels a specific confirmed reservation for the logged-in user.
    """
    if request.method == "POST":
        reservation = get_object_or_404(
            Reservation,
            user=request.user,
            uuid=reservation_id,
        )

        try:
            ReservationService(reservation).admin.cancel(request.user)
            messages.success(
                request,
                f"Your reservation for '{reservation.event.service.name}' "
                f"on {reservation.event.start_datetime.date()} has been cancelled.",
            )
        except ValidationError as e:
            for message in e.messages:
                messages.error(request, message)
        except Exception as e:
            messages.error(request, f"An error occurred while cancelling: {e}")

        context = get_reservation_list_context(request.user)
        return render(
            request,
            "phoxtail_booking_reservations/list/partials/reservations.html",
            context,
        )

    return HttpResponse("Invalid request", status=400)


@login_required
def waitlisted_reservation_cancel_form_view(request, reservation_id):
    """
    Displays waitlisted reservation details in a modal when clicking a waitlisted reservation from the list.
    Returns the waitlisted reservation content for modal display.
    """
    reservation = get_object_or_404(
        Reservation,
        uuid=reservation_id,
        user=request.user,
        status=ReservationStatus.WAITLISTED,
    )
    context = {"reservation": reservation}
    return render(
        request,
        "phoxtail_booking_reservations/list/partials/forms/waitlisted_reservation_cancel_form.html",
        context,
    )


@login_required
def waitlisted_reservation_cancel_view(request, reservation_id):
    """
    Cancels (deletes) a waitlisted reservation for the logged-in user.
    Waitlisted reservations are simply deleted since no credits were used.
    """
    if request.method == "POST":
        reservation = get_object_or_404(
            Reservation,
            uuid=reservation_id,
            user=request.user,
            status=ReservationStatus.WAITLISTED,
        )

        try:
            # Store event info for success message before deletion
            event_service_name = reservation.event.service.name
            event_date = reservation.event.start_datetime.date()

            # Simply delete the waitlisted reservation - no credit restoration needed
            reservation.delete()

            messages.success(
                request,
                f"You have been removed from the waitlist for '{event_service_name}' "
                f"on {event_date}.",
            )
        except Exception as e:
            messages.error(
                request, f"An error occurred while leaving the waitlist: {e}"
            )

        context = get_reservation_list_context(request.user)
        return render(
            request,
            "phoxtail_booking_reservations/list/partials/reservations.html",
            context,
        )

    return HttpResponse("Invalid request", status=400)


@login_required
def waitlisted_reservation_confirm_form_view(request, reservation_id):
    """
    Displays waitlisted reservation confirmation form when a spot becomes available.
    Shows the bound subscription and allows confirming or leaving waitlist.
    """
    reservation = get_object_or_404(
        Reservation.objects.select_related(
            "subscription",
            "subscription__subscription_type",
        ),
        uuid=reservation_id,
        user=request.user,
        status=ReservationStatus.WAITLISTED,
    )

    event = reservation.event

    # Check if there's actually a spot available
    if event.is_full:
        # Redirect back to regular waitlist form if no spots available
        return waitlisted_reservation_cancel_form_view(request, reservation_id)

    context = {
        "reservation": reservation,
        "event": event,
    }
    return render(
        request,
        "phoxtail_booking_reservations/list/partials/forms/waitlisted_reservation_confirm_form.html",
        context,
    )


@login_required
def waitlisted_reservation_confirm_view(request, reservation_id):
    """
    Confirms a waitlisted reservation by changing status to CONFIRMED and using credits.
    """
    if request.method == "POST":
        subscription_id = request.POST.get("subscription_id")

        try:
            reservation = ReservationService().public.confirm_waitlisted(
                user=request.user,
                reservation_id=reservation_id,
                subscription_id=subscription_id,
            )
            messages.success(
                request,
                f"Great! You've successfully confirmed your spot for '{reservation.event.service.name}' "
                f"on {reservation.event.start_datetime.date()}!",
            )
        except ValidationError as e:
            for message in e.messages:
                messages.error(request, message)
        except Exception as e:
            messages.error(request, f"An unexpected error occurred: {e}")

        context = get_reservation_list_context(request.user)
        return render(
            request,
            "phoxtail_booking_reservations/list/partials/reservations.html",
            context,
        )

    return HttpResponse("Invalid request", status=400)
