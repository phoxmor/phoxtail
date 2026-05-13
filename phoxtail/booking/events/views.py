from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render

from phoxtail.booking.events.models import Event
from phoxtail.booking.reservations.constants import ReservationStatus
from phoxtail.booking.reservations.models import Reservation
from phoxtail.booking.reservations.services import ReservationService
from phoxtail.booking.subscriptions.models import Subscription

from .utils import BookingContextBuilder


# Filters
@login_required
def booking_filters_form_view(request):
    """
    Displays the filters modal for the booking view.
    Uses lightweight filter context only - no expensive events query.
    """
    context = BookingContextBuilder.get_filters_context(request)

    return render(
        request,
        "phoxtail_booking_events/public/booking/partials/forms/filters/form.html",
        context,
    )


@login_required
def booking_filters_view(request):
    """
    Processes filter changes and returns OOB swaps to update both the calendar and the filters form.
    This allows filter state to be managed server-side without JavaScript.
    """
    context = BookingContextBuilder.get_full_context(request)

    return render(
        request,
        "phoxtail_booking_events/public/booking/partials/forms/filters/form_response.html",
        context,
    )


# Create and cancel new CONFIRMED reservations
@login_required
def event_list_view(request: HttpRequest):
    """
    Displays events in a week view calendar with week navigation.
    """
    # Use the shared calendar context function
    context = BookingContextBuilder.get_full_context(request)

    # Determine if it's an HTMX request
    is_htmx_request = bool(request.htmx)
    context["is_htmx_request"] = is_htmx_request

    if is_htmx_request:
        # Render the calendar partial for HTMX requests
        return render(
            request,
            "phoxtail_booking_events/public/booking/partials/calendar.html",
            context,
        )

    # Render the main index.html for initial page load
    return render(request, "phoxtail_booking_events/public/booking/index.html", context)


@login_required
def event_reservation_create_form_view(request):
    """
    Renders the reservation confirmation form to be loaded into a modal via HTMX.
    This view only handles GET requests to display the form.
    It fetches the user's active subscriptions for the event.
    """
    event_id = request.GET.get("event_id")
    event = get_object_or_404(Event, uuid=event_id)

    # Get user's subscriptions that can access this event's service
    eligible_user_subscriptions = (
        Subscription.objects.can_access_service(event.service)
        .filter(
            user=request.user,
        )
        .prefetch_related("subscription_type__credit_allocations")
    )

    context = {
        "event": event,
        "eligible_user_subscriptions": eligible_user_subscriptions,
    }
    return render(
        request,
        "phoxtail_booking_events/public/booking/partials/forms/create/event_reservation_create_form.html",
        context,
    )


@login_required
def event_reservation_create_view(request):
    if request.method == "POST":
        event_id = request.POST.get("event_id")
        subscription_id = request.POST.get("subscription_id")

        if not event_id:
            messages.error(request, "Event ID is required.")
            return HttpResponse(headers={"HX-Refresh": "true"})

        try:
            reservation = ReservationService().public.create(
                user=request.user,
                event_id=event_id,
                subscription_id=subscription_id,
            )
            messages.success(
                request,
                f"You have successfully reserved a spot for '{reservation.event.service.name}' "
                f"on {reservation.event.start_datetime.date()}!",
            )
        except ValidationError as e:
            for message in e.messages:
                messages.error(request, message)
        except Exception as e:
            messages.error(request, f"An unexpected error occurred: {e}")

        context = BookingContextBuilder.get_full_context(request)
        return render(
            request,
            "phoxtail_booking_events/public/booking/partials/calendar.html",
            context,
        )

    return HttpResponse("Invalid request", status=400)


@login_required
def event_reservation_cancel_form_view(request, reservation_id):
    """
    Displays reservation details in a modal when clicking a booked event from the calendar.
    Returns only the reservation content without dashboard layout for modal display.
    """
    reservation = get_object_or_404(Reservation, uuid=reservation_id, user=request.user)

    context = {"reservation": reservation}
    return render(
        request,
        "phoxtail_booking_events/public/booking/partials/forms/cancel/event_reservation_cancel_form.html",
        context,
    )


@login_required
def event_reservation_cancel_view(request, reservation_id):
    """
    Cancels a specific reservation for the logged-in user.
    """
    if request.method == "POST":
        reservation = get_object_or_404(Reservation, uuid=reservation_id, user=request.user)

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

        context = BookingContextBuilder.get_full_context(request)
        return render(
            request,
            "phoxtail_booking_events/public/booking/partials/calendar.html",
            context,
        )

    return HttpResponse("Invalid request", status=400)


# Create and cancel new WAITLISTED reservations
@login_required
def event_waitlisted_reservation_create_form_view(request):
    event_id = request.GET.get("event_id")
    event = get_object_or_404(Event, uuid=event_id)

    # Get user's subscriptions that can access this event's service
    eligible_user_subscriptions = (
        Subscription.objects.can_access_service(event.service)
        .filter(
            user=request.user,
        )
        .prefetch_related("subscription_type__credit_allocations")
    )

    context = {
        "event": event,
        "eligible_user_subscriptions": eligible_user_subscriptions,
    }
    return render(
        request,
        "phoxtail_booking_events/public/booking/partials/forms/create/event_waitlisted_reservation_create_form.html",
        context,
    )


@login_required
def event_waitlisted_reservation_create_view(request):
    """
    Creates a waitlisted reservation for the user when the event is full.
    """
    if request.method == "POST":
        event_id = request.POST.get("event_id")
        subscription_id = request.POST.get("subscription_id")

        if not event_id:
            messages.error(request, "Event ID is required.")
            return HttpResponse(headers={"HX-Refresh": "true"})

        if not subscription_id:
            messages.error(request, "Subscription selection is required.")
            return HttpResponse(headers={"HX-Refresh": "true"})

        try:
            reservation = ReservationService().public.create_waitlisted(
                user=request.user,
                event_id=event_id,
                subscription_id=subscription_id,
            )
            messages.success(
                request,
                f"You have been added to the waitlist for '{reservation.event.service.name}' "
                f"on {reservation.event.start_datetime.date()}! You'll be notified if a spot becomes available.",
            )
        except ValidationError as e:
            for message in e.messages:
                messages.error(request, message)
        except Exception as e:
            messages.error(request, f"An unexpected error occurred: {e}")

        context = BookingContextBuilder.get_full_context(request)
        return render(
            request,
            "phoxtail_booking_events/public/booking/partials/calendar.html",
            context,
        )

    return HttpResponse("Invalid request", status=400)


@login_required
def event_waitlisted_reservation_cancel_form_view(request, reservation_id):
    """
    Displays waitlisted reservation details in a modal when clicking a waitlisted event from the calendar.
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
        "phoxtail_booking_events/public/booking/partials/forms/cancel/event_waitlisted_reservation_cancel_form.html",
        context,
    )


@login_required
def event_waitlisted_reservation_cancel_view(request, reservation_id):
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
                f"You have been removed from the waitlist for '{event_service_name}' on {event_date}.",
            )
        except Exception as e:
            messages.error(request, f"An error occurred while leaving the waitlist: {e}")

        context = BookingContextBuilder.get_full_context(request)
        return render(
            request,
            "phoxtail_booking_events/public/booking/partials/calendar.html",
            context,
        )

    return HttpResponse("Invalid request", status=400)


@login_required
def event_waitlisted_reservation_confirm_form_view(request, reservation_id):
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
        return event_waitlisted_reservation_cancel_form_view(request, reservation_id)

    context = {
        "reservation": reservation,
        "event": event,
    }
    return render(
        request,
        "phoxtail_booking_events/public/booking/partials/forms/confirm/event_waitlisted_reservation_confirm_form.html",
        context,
    )


@login_required
def event_waitlisted_reservation_confirm_view(request, reservation_id):
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

        context = BookingContextBuilder.get_full_context(request)
        return render(
            request,
            "phoxtail_booking_events/public/booking/partials/calendar.html",
            context,
        )

    return HttpResponse("Invalid request", status=400)
