"""
Admin operation: update a template event (recurrence template).
"""

from typing import TYPE_CHECKING

from django.db import transaction

from ...validation import (
    ValidationResult,
    validate_monthly_recurrence,
    validate_recurrence_until,
    validate_time_range,
)

if TYPE_CHECKING:
    from ....models import Event
    from ...base import EventService


class EventServiceAdminUpdateTemplate:
    """
    Admin domain operation for template event updates.

    Template events define the recurrence pattern for a series. Updates affect
    how future events are generated but do not modify existing generated events.

    Projected event conflict checks are intentionally omitted — the conflict-aware
    recurrence generation (generate_recurring_events) handles those at generation
    time by skipping occupied slots.
    """

    def __init__(self, service: "EventService") -> None:
        self.service = service

    def authorize(self) -> None:
        pass

    def validate(self, **data) -> ValidationResult:
        event = self.service.event
        result = ValidationResult()

        start_datetime = data.get("start_datetime", event.start_datetime)
        end_datetime = data.get("end_datetime", event.end_datetime)

        # Hard errors: time range
        result.merge(validate_time_range(start_datetime, end_datetime))

        # Hard errors: recurrence settings
        recurrence_until = data.get("recurrence_until", event.recurrence_until)
        result.merge(validate_recurrence_until(start_datetime, recurrence_until))

        result.merge(
            validate_monthly_recurrence(
                data.get("recurrence_freq", event.recurrence_freq),
                data.get("recurrence_bymonthday", event.recurrence_bymonthday),
                data.get("recurrence_bysetpos", event.recurrence_bysetpos),
                data.get(
                    "recurrence_byweekday_monthly",
                    event.recurrence_byweekday_monthly,
                ),
            )
        )

        return result

    def perform(self, **data) -> "Event":
        event = self.service.event

        with transaction.atomic():
            staff = data.pop("staff", None)

            for field, value in data.items():
                setattr(event, field, value)

            event.save()

            if staff is not None:
                event.staff.set(staff)

            return event

    def execute(self, force: bool = True, **data) -> "Event":
        self.authorize()
        result = self.validate(**data)
        result.raise_if_errors()
        if not force:
            result.raise_if_warnings()
        return self.perform(**data)
