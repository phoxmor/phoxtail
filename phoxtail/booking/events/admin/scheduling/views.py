from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, render

from phoxtail.booking.core.permissions import booking_permission_required
from phoxtail.booking.events.constants import EventUpdateScope, RecurrenceFrequency
from phoxtail.booking.events.models import Event

from ..utils import ScheduleContextBuilder


@booking_permission_required("access_scheduling_management", "create_scheduled_events")
def admin_schedule_event_create_form_view(request):
    """
    Displays the create event form in the scheduling section for admin to create new events.
    Handles both GET (display form) and POST (process form) requests.
    Accepts optional date, hour, and location parameters to prefill start_datetime, end_datetime,
    and filter spaces by location.
    """
    from datetime import datetime, timedelta

    from phoxtail.booking.core.models import Location
    from phoxtail.booking.events.forms import EventCreateForm

    # Extract location from GET or POST parameters
    location_id = request.GET.get("location") or request.POST.get("location")
    location = None
    if location_id:
        try:
            location = Location.objects.get(id=location_id, is_active=True)
        except (Location.DoesNotExist, ValidationError):
            # Invalid location ID, proceed without location filtering
            pass

    if request.method == "POST":
        form = EventCreateForm(request.POST, location=location)
        if form.is_valid():
            try:
                event = form.save()
                messages.success(
                    request,
                    f"Event '{event.service.name}' successfully created"
                    f" for {event.start_datetime.strftime('%B %d, %Y at %I:%M %p')}.",
                )
                # Surface soft warnings as info messages
                for warn in getattr(form, "_warnings", []):
                    messages.warning(request, warn.message)
            except ValidationError as e:
                for message in e.messages:
                    messages.error(request, message)
        else:
            # Form has errors, add to messages
            for errors in form.errors.values():
                for error in errors:
                    messages.error(request, error)

        schedule_context = ScheduleContextBuilder.get_full_context(request)
        context = {
            "form": form,
            **schedule_context,
        }

        return render(
            request,
            "phoxtail_booking_events/admin/scheduling/partials/forms/create/event_response.html",
            context,
        )
    else:
        # Check for date and hour parameters to prefill the form
        initial_data = {}
        date_param = request.GET.get("date")
        hour_param = request.GET.get("hour")

        if date_param and hour_param:
            try:
                # Parse the date (format: YYYY-MM-DD)
                event_date = datetime.strptime(date_param, "%Y-%m-%d").date()
                hour = int(hour_param)

                # Create start_datetime (date + hour) - timezone-naive for the form
                start_datetime = datetime.combine(event_date, datetime.min.time()).replace(hour=hour)

                # Create end_datetime (1 hour later by default)
                end_datetime = start_datetime + timedelta(hours=1)

                # Format for datetime-local input (YYYY-MM-DDTHH:MM)
                # Note: datetime-local inputs expect timezone-naive values
                initial_data["start_datetime"] = start_datetime.strftime("%Y-%m-%dT%H:%M")
                initial_data["end_datetime"] = end_datetime.strftime("%Y-%m-%dT%H:%M")
            except (ValueError, TypeError):
                # Invalid date/hour format, ignore and show empty form
                pass

        form = EventCreateForm(initial=initial_data, location=location)

    context = {
        "form": form,
    }

    return render(
        request,
        "phoxtail_booking_events/admin/scheduling/partials/forms/create/event.html",
        context,
    )


@booking_permission_required("access_scheduling_management", "edit_scheduled_events")
def admin_schedule_event_update_form_view(request, event_id):
    """
    Displays the update event form in the scheduling section for admin to edit existing events.
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
                # Surface soft warnings as info messages
                for warn in getattr(form, "_warnings", []):
                    messages.warning(request, warn.message)
            except ValidationError as e:
                for message in e.messages:
                    messages.error(request, message)
        else:
            # Form has errors, add to messages
            for errors in form.errors.values():
                for error in errors:
                    messages.error(request, error)

        schedule_context = ScheduleContextBuilder.get_full_context(request)
        context = {
            "form": form,
            "event": event,
            **schedule_context,
        }

        return render(
            request,
            "phoxtail_booking_events/admin/scheduling/partials/forms/update/event/form_response.html",
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
        "phoxtail_booking_events/admin/scheduling/partials/forms/update/event/form.html",
        context,
    )


@booking_permission_required("access_scheduling_management")
def admin_event_schedule_view(request):
    """
    Displays events in a simplified week schedule view.
    Shows only service name and time for each event across 7 days.
    """
    context = ScheduleContextBuilder.get_full_context(request)

    is_htmx_request = bool(request.htmx)
    context["is_htmx_request"] = is_htmx_request

    if is_htmx_request:
        return render(
            request,
            "phoxtail_booking_events/admin/scheduling/partials/schedule.html",
            context,
        )

    return render(request, "phoxtail_booking_events/admin/scheduling/index.html", context)


@booking_permission_required("access_scheduling_management")
def admin_schedule_event_capacity_form_field_view(request):
    """
    HTMX endpoint for rendering the capacity form field when a space is selected.
    Returns a rendered capacity input field pre-filled with the space's default capacity.
    """
    from phoxtail.booking.core.models import Space
    from phoxtail.booking.events.forms import EventCreateForm

    space_id = request.GET.get("space")
    capacity_value = None

    if space_id:
        try:
            space = Space.objects.get(id=space_id, is_active=True)
            capacity_value = space.capacity
        except (Space.DoesNotExist, ValidationError):
            # Invalid space ID, return empty capacity
            pass

    # Create a form instance with initial capacity value
    initial_data = {"capacity": capacity_value} if capacity_value is not None else {}
    form = EventCreateForm(initial=initial_data)

    context = {
        "field": form["capacity"],
    }

    return render(
        request,
        "phoxtail_core/forms/widgets/number.html",
        context,
    )


@booking_permission_required("access_scheduling_management")
def admin_schedule_event_frequency_form_field_view(request):
    """
    HTMX endpoint for rendering the frequency field with dynamic pluralization.

    Triggered by: interval field changes
    Returns: Only the frequency <select> field

    Behavior:
    - If interval > 1: pluralize labels ("Day" → "Days", "Week" → "Weeks")
    - If interval == 1: singular labels ("Day", "Week")
    - Preserves the selected frequency value from request
    """
    from django import forms as django_forms

    from phoxtail.booking.events.forms import EventCreateForm

    recurrence_freq = request.GET.get("recurrence_freq")
    recurrence_interval = request.GET.get("recurrence_interval")

    pluralize_freq = False

    # Determine if we should pluralize frequency labels
    if recurrence_interval:
        try:
            interval_value = int(recurrence_interval)
            pluralize_freq = interval_value > 1
        except (ValueError, TypeError):
            pluralize_freq = False

    # Create unbound form with initial values to preserve user's frequency selection
    initial_data = {}
    if recurrence_freq:
        initial_data["recurrence_freq"] = recurrence_freq

    form = EventCreateForm(initial=initial_data)

    # Pluralize frequency choices if needed
    if pluralize_freq:
        freq_field = form.fields["recurrence_freq"]
        # Create pluralized choices: "Day" → "Days", "Week" → "Weeks"
        new_choices = [(value, f"{label}s") for value, label in RecurrenceFrequency.choices]
        # Preserve the empty choice for non-required fields
        if not freq_field.required:
            new_choices = [("", "---------")] + new_choices
        # Recreate the widget with new choices
        freq_field.widget = django_forms.Select(choices=new_choices)
        freq_field.choices = new_choices
    else:
        # Even when not pluralizing, ensure empty choice is present
        freq_field = form.fields["recurrence_freq"]
        if not freq_field.required and not any(choice[0] == "" for choice in freq_field.choices):
            base_choices = list(RecurrenceFrequency.choices)
            freq_field.widget = django_forms.Select(choices=[("", "---------")] + base_choices)
            freq_field.choices = [("", "---------")] + base_choices

    from django.urls import reverse

    context = {
        "field": form["recurrence_freq"],
        "show_label": False,
        "show_help_text": False,
        "hx_get": reverse("scheduling_management:admin_schedule_event_weekdays_form_field"),
        "hx_target": "#recurrence-frequency-dependent-wrapper",
        "hx_vals": "js:{recurrence_interval: document.getElementById('id_recurrence_interval').value}",
    }

    return render(
        request,
        "phoxtail_core/forms/widgets/htmx/select.html",
        context,
    )


@booking_permission_required("access_scheduling_management")
def admin_schedule_event_weekdays_form_field_view(request):
    """
    HTMX endpoint for rendering frequency-dependent fields (weekdays + monthly options).

    Triggered by: frequency field changes
    Returns: Combined wrapper with weekdays (if WEEKLY) and monthly options (if MONTHLY)

    Behavior:
    - If frequency == WEEKLY: show weekday checkboxes
    - If frequency == MONTHLY: show monthly recurrence options
    - Otherwise: return empty divs
    """
    from phoxtail.booking.events.forms import EventCreateForm

    recurrence_freq = request.GET.get("recurrence_freq")

    show_weekdays = False
    show_monthly_options = False

    # Determine what to show based on frequency
    if recurrence_freq:
        try:
            freq_value = int(recurrence_freq)
            # Show weekdays only for WEEKLY frequency
            show_weekdays = freq_value == RecurrenceFrequency.WEEKLY
            # Show monthly options only for MONTHLY frequency
            show_monthly_options = freq_value == RecurrenceFrequency.MONTHLY
        except (ValueError, TypeError):
            # Invalid frequency, default to hiding both
            pass

    # Create unbound form
    form = EventCreateForm()

    context = {
        "form": form,
        "show_weekdays": show_weekdays,
        "show_monthly_options": show_monthly_options,
    }

    return render(
        request,
        "phoxtail_booking_events/admin/scheduling/partials/forms/components/frequency_dependent_fields.html",
        context,
    )


@booking_permission_required("access_scheduling_management")
def admin_schedule_filters_form_view(request):
    """
    Displays the filters modal for the schedule view (filters only, no actions).
    Uses lightweight filter context only - no expensive schedule structure building.
    """

    context = ScheduleContextBuilder.get_filters_context(request)

    return render(
        request,
        "phoxtail_booking_events/admin/scheduling/partials/forms/filters/form.html",
        context,
    )


@booking_permission_required("access_scheduling_management")
def admin_schedule_filters_view(request):
    """
    Processes filter changes and returns OOB swaps to update both the schedule and the filters form.
    This allows filter state to be managed server-side without JavaScript.
    """
    context = ScheduleContextBuilder.get_full_context(request)

    return render(
        request,
        "phoxtail_booking_events/admin/scheduling/partials/forms/filters/form_response.html",
        context,
    )


@booking_permission_required("access_scheduling_management")
def admin_schedule_actions_form_view(request):
    """
    Displays the actions modal for the schedule view (actions only, no filters).
    Uses lightweight filter context only - no expensive schedule structure building.
    """

    context = ScheduleContextBuilder.get_filters_context(request)

    return render(
        request,
        "phoxtail_booking_events/admin/scheduling/partials/forms/actions/form.html",
        context,
    )


@booking_permission_required("access_scheduling_management", "bulk_update_scheduled_events")
def admin_schedule_actions_view(request):
    """
    Processes action changes (show_empty_rows) and returns OOB swaps to update both the schedule and the actions form.
    This allows action state to be managed server-side without JavaScript.
    """
    context = ScheduleContextBuilder.get_full_context(request)

    return render(
        request,
        "phoxtail_booking_events/admin/scheduling/partials/forms/actions/form_response.html",
        context,
    )


@booking_permission_required("access_scheduling_management", "delete_scheduled_events")
def admin_schedule_event_delete_view(request, event_id):
    """
    Handles event deletion from the scheduling section.
    Supports single event, this-and-future, and all-in-series scopes.
    POST only.
    """
    from phoxtail.booking.events.services import EventService

    event = get_object_or_404(Event, uuid=event_id)

    if request.method == "POST":
        delete_scope = request.POST.get("update_scope", EventUpdateScope.THIS_EVENT_ONLY)

        service_name = event.service.name

        try:
            deleted_count = EventService(event).admin.delete(delete_scope=delete_scope)

            if delete_scope == EventUpdateScope.ALL_EVENTS_IN_SERIES:
                messages.success(
                    request,
                    f"Successfully deleted the entire '{service_name}' series "
                    f"({deleted_count} event(s) including template).",
                )
            elif delete_scope == EventUpdateScope.THIS_AND_FUTURE_EVENTS:
                messages.success(
                    request,
                    f"Successfully deleted {deleted_count} future event(s) "
                    f"in the '{service_name}' series. The series has been "
                    f"ended at this date.",
                )
            else:
                messages.success(
                    request,
                    f"Event '{service_name}' on "
                    f"{event.start_datetime.strftime('%B %d, %Y at %I:%M %p')} "
                    f"successfully deleted.",
                )
        except ValidationError as e:
            for message in e.messages:
                messages.error(request, message)

    schedule_context = ScheduleContextBuilder.get_full_context(request)

    return render(
        request,
        "phoxtail_booking_events/admin/scheduling/partials/forms/delete/event_response.html",
        schedule_context,
    )


@booking_permission_required("access_scheduling_management", "edit_scheduled_events")
def admin_schedule_template_event_update_form_view(request, event_id):
    """
    Displays the update template event form for editing recurring series templates.
    Handles both GET (display form) and POST (process form) requests.
    Only works with template events (is_recurrence_template=True).
    """
    from phoxtail.booking.events.forms import TemplateEventUpdateForm

    template_event = get_object_or_404(Event, uuid=event_id, is_recurrence_template=True)

    if request.method == "POST":
        form = TemplateEventUpdateForm(request.POST, instance=template_event)
        if form.is_valid():
            try:
                template_event = form.save()
                messages.success(
                    request,
                    f"Series template for '{template_event.service.name}' successfully updated."
                    " Future generated events will inherit these changes.",
                )
                # Surface soft warnings as info messages
                for warn in getattr(form, "_warnings", []):
                    messages.warning(request, warn.message)
            except ValidationError as e:
                for message in e.messages:
                    messages.error(request, message)
        else:
            # Form has errors, add to messages
            for errors in form.errors.values():
                for error in errors:
                    messages.error(request, error)

        # Determine which frequency-dependent fields to show (needed for error re-render)
        show_weekdays = template_event.recurrence_freq == RecurrenceFrequency.WEEKLY
        show_monthly_options = template_event.recurrence_freq == RecurrenceFrequency.MONTHLY

        schedule_context = ScheduleContextBuilder.get_full_context(request)
        context = {
            "form": form,
            "template_event": template_event,
            "show_weekdays": show_weekdays,
            "show_monthly_options": show_monthly_options,
            **schedule_context,
        }

        return render(
            request,
            "phoxtail_booking_events/admin/scheduling/partials/forms/update/template/form_response.html",
            context,
        )
    else:
        form = TemplateEventUpdateForm(instance=template_event)

        # Pluralize frequency field choices if interval > 1 on initial load
        if template_event.recurrence_interval and template_event.recurrence_interval > 1:
            from django import forms

            freq_field = form.fields["recurrence_freq"]
            new_choices = [(value, f"{label}s") for value, label in RecurrenceFrequency.choices]
            if not freq_field.required:
                new_choices = [("", "---------")] + new_choices
            freq_field.widget = forms.Select(choices=new_choices)
            freq_field.choices = new_choices

    # Determine which frequency-dependent fields to show on initial load
    show_weekdays = template_event.recurrence_freq == RecurrenceFrequency.WEEKLY
    show_monthly_options = template_event.recurrence_freq == RecurrenceFrequency.MONTHLY

    context = {
        "form": form,
        "template_event": template_event,
        "show_weekdays": show_weekdays,
        "show_monthly_options": show_monthly_options,
    }

    return render(
        request,
        "phoxtail_booking_events/admin/scheduling/partials/forms/update/template/form.html",
        context,
    )


@booking_permission_required("access_scheduling_management", "bulk_update_scheduled_events")
def admin_schedule_bulk_update_status_form_view(request):
    """
    Displays the bulk update status form modal for the schedule view.
    Allows admins to update event statuses for all events within a date range.
    """
    from phoxtail.booking.events.forms import EventBulkUpdateStatusForm

    if request.method == "POST":
        form = EventBulkUpdateStatusForm(request.POST)
        if form.is_valid():
            # Get the date range and new status
            from_datetime = form.cleaned_data["from_datetime"]
            to_datetime = form.cleaned_data["to_datetime"]
            new_status = form.cleaned_data["status"]

            # Update all events in the date range
            events_to_update = Event.objects.filter(start_datetime__gte=from_datetime, start_datetime__lte=to_datetime)

            updated_count = events_to_update.update(status=new_status)

            # Add success message
            messages.success(
                request,
                f"Successfully updated {updated_count} event(s) to {new_status}.",
            )

            # Return context for OOB swap to refresh the schedule
            context = ScheduleContextBuilder.get_full_context(request)
            return render(
                request,
                "phoxtail_booking_events/admin/scheduling/partials/forms/update/bulk/status/form_response.html",
                context,
            )
    else:
        form = EventBulkUpdateStatusForm()

    context = {"form": form}
    return render(
        request,
        "phoxtail_booking_events/admin/scheduling/partials/forms/update/bulk/status/form.html",
        context,
    )
