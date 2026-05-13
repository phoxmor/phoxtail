"""
Admin operation: create a new event.
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


class EventServiceAdminCreate:
    """
    Admin domain operation for event creation.

    Follows the authorize / validate / perform / execute lifecycle.
    """

    def __init__(self, service: "EventService") -> None:
        self.service = service

    def authorize(self) -> None:
        pass

    def validate(self, **data) -> ValidationResult:
        from ....models import Event
        from ...base import EventService

        result = ValidationResult()

        start_datetime = data.get("start_datetime")
        end_datetime = data.get("end_datetime")
        space = data.get("space")

        # Hard errors: time range
        result.merge(validate_time_range(start_datetime, end_datetime))

        # Hard errors: recurrence settings
        result.merge(validate_recurrence_until(start_datetime, data.get("recurrence_until")))
        result.merge(
            validate_monthly_recurrence(
                data.get("recurrence_freq"),
                data.get("recurrence_bymonthday"),
                data.get("recurrence_bysetpos"),
                data.get("recurrence_byweekday_monthly"),
            )
        )

        # Stop early if hard errors already found
        if result.has_errors:
            return result

        # Soft warnings: space-time conflict with real events
        if start_datetime and end_datetime and space:
            conflicting_events = Event.objects.filter(
                space=space,
                start_datetime__lt=end_datetime,
                end_datetime__gt=start_datetime,
                is_recurrence_template=False,
            )

            if conflicting_events.exists():
                conflict = conflicting_events.first()
                event_tz = space.location.timezone
                conflict_start_local = conflict.start_datetime.astimezone(event_tz)
                conflict_end_local = conflict.end_datetime.astimezone(event_tz)
                result.add_warning(
                    f"This time slot conflicts with an existing event: "
                    f"{conflict.service.name} "
                    f"({conflict_start_local.strftime('%Y-%m-%d %H:%M')} - "
                    f"{conflict_end_local.strftime('%H:%M')}) in {space.name}.",
                    field="start_datetime",
                )

        # Soft warning: staff double-booking
        if start_datetime and end_datetime:
            staff_members = data.get("staff", [])
            if space and staff_members:
                temp_event = Event(
                    space=space,
                    start_datetime=start_datetime,
                    end_datetime=end_datetime,
                )
                result.merge(
                    EventService.validate_staff_availability(
                        temp_event,
                        start_datetime,
                        end_datetime,
                        staff_members,
                        events_to_exclude=[],
                    )
                )

        return result

    def perform(self, **data) -> "Event":
        from ....models import Event

        with transaction.atomic():
            staff = data.pop("staff", None)

            if data.get("recurrence_freq"):
                data["is_recurrence_template"] = True

            event = Event.objects.create(**data)

            if staff:
                event.staff.set(staff)

            return event

    def execute(self, force: bool = True, **data) -> "Event":
        self.authorize()
        result = self.validate(**data)
        result.raise_if_errors()
        if not force:
            result.raise_if_warnings()
        return self.perform(**data)
