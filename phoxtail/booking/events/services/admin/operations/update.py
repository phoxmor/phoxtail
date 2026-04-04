"""
Admin operation: update an existing event (single, this-and-future, all-in-series).
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


class EventServiceAdminUpdate:
    """
    Admin domain operation for event updates.

    Supports three scopes:
      - THIS_EVENT_ONLY (default)
      - THIS_AND_FUTURE_EVENTS
      - ALL_EVENTS_IN_SERIES
    """

    def __init__(self, service: "EventService") -> None:
        self.service = service

    def authorize(self) -> None:
        pass

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate(self, update_scope: str | None = None, **data) -> ValidationResult:
        from ....constants import EventUpdateScope
        from ....models import Event

        event = self.service.event
        result = ValidationResult()

        if update_scope is None or update_scope not in EventUpdateScope.values:
            update_scope = EventUpdateScope.THIS_EVENT_ONLY

        start_datetime = data.get("start_datetime", event.start_datetime)
        end_datetime = data.get("end_datetime", event.end_datetime)
        space = data.get("space", event.space)

        # Hard errors: time range
        result.merge(validate_time_range(start_datetime, end_datetime))

        # Hard errors: recurrence settings
        recurrence_until = data.get(
            "recurrence_until", event.recurrence_until if event.pk else None
        )
        result.merge(validate_recurrence_until(start_datetime, recurrence_until))

        result.merge(
            validate_monthly_recurrence(
                data.get(
                    "recurrence_freq",
                    event.recurrence_freq if event.pk else None,
                ),
                data.get(
                    "recurrence_bymonthday",
                    event.recurrence_bymonthday if event.pk else None,
                ),
                data.get(
                    "recurrence_bysetpos",
                    event.recurrence_bysetpos if event.pk else None,
                ),
                data.get(
                    "recurrence_byweekday_monthly",
                    event.recurrence_byweekday_monthly if event.pk else None,
                ),
            )
        )

        if result.has_errors:
            return result

        # Soft warnings: space-time and staff conflicts
        events_to_update = None
        if start_datetime and end_datetime and space:
            # Determine events_to_update for bulk scopes
            events_to_update = None
            if (
                event.recurrence_template or event.is_recurrence_template
            ) and update_scope != EventUpdateScope.THIS_EVENT_ONLY:
                template = (
                    event if event.is_recurrence_template else event.recurrence_template
                )

                if update_scope == EventUpdateScope.THIS_AND_FUTURE_EVENTS:
                    original_start_datetime = Event.objects.get(
                        pk=event.pk
                    ).start_datetime
                    events_to_update = Event.objects.filter(
                        recurrence_template=template,
                        is_recurrence_template=False,
                        start_datetime__gte=original_start_datetime,
                    ).order_by("start_datetime")
                elif update_scope == EventUpdateScope.ALL_EVENTS_IN_SERIES:
                    events_to_update = Event.objects.filter(
                        recurrence_template=template,
                        is_recurrence_template=False,
                    ).order_by("start_datetime")

            if events_to_update is not None:
                result.merge(
                    self._validate_bulk_update_conflicts(
                        event, data, events_to_update, space
                    )
                )
            else:
                result.merge(
                    self._validate_single_update_conflict(
                        event, start_datetime, end_datetime, space
                    )
                )

        # Soft warnings: staff availability (single update only)
        if start_datetime and end_datetime and events_to_update is None:
            from ...base import EventService

            staff_members = data.get("staff", event.staff.all() if event.pk else [])
            events_to_exclude = [event.pk] if event.pk else []
            result.merge(
                EventService.validate_staff_availability(
                    event,
                    start_datetime,
                    end_datetime,
                    staff_members,
                    events_to_exclude,
                )
            )

        return result

    # ------------------------------------------------------------------
    # Perform
    # ------------------------------------------------------------------

    def perform(self, update_scope: str | None = None, **data) -> tuple["Event", int]:
        from ....constants import EventUpdateScope

        event = self.service.event

        if update_scope is None or update_scope not in EventUpdateScope.values:
            update_scope = EventUpdateScope.THIS_EVENT_ONLY

        if not event.recurrence_template and not event.is_recurrence_template:
            return self._perform_single_update(event, **data)

        if update_scope == EventUpdateScope.THIS_EVENT_ONLY:
            return self._perform_single_update(event, **data)
        elif update_scope == EventUpdateScope.THIS_AND_FUTURE_EVENTS:
            return self._perform_this_and_future_update(event, **data)
        elif update_scope == EventUpdateScope.ALL_EVENTS_IN_SERIES:
            return self._perform_all_in_series_update(event, **data)

    def execute(
        self,
        update_scope: str | None = None,
        force: bool = True,
        **data,
    ) -> tuple["Event", int]:
        self.authorize()
        result = self.validate(update_scope=update_scope, **data)
        result.raise_if_errors()
        if not force:
            result.raise_if_warnings()
        return self.perform(update_scope=update_scope, **data)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_times_from_data(event: "Event", data: dict) -> tuple:
        """Extract time-of-day values from update data in the event's local timezone."""
        event_tz = event.space.location.timezone
        new_start_datetime = None
        new_end_datetime = None

        if "start_datetime" in data:
            new_start_datetime = data["start_datetime"].astimezone(event_tz).time()

        if "end_datetime" in data:
            new_end_datetime = data["end_datetime"].astimezone(event_tz).time()

        return new_start_datetime, new_end_datetime

    @staticmethod
    def _apply_updates_to_event(
        event: "Event", data: dict, new_start_datetime, new_end_datetime, staff
    ) -> None:
        """Apply field updates to a single event instance."""
        event_tz = event.space.location.timezone

        if new_start_datetime is not None:
            local_dt = event.start_datetime.astimezone(event_tz)
            local_dt = local_dt.replace(
                hour=new_start_datetime.hour,
                minute=new_start_datetime.minute,
                second=new_start_datetime.second,
                microsecond=new_start_datetime.microsecond,
            )
            event.start_datetime = local_dt

        if new_end_datetime is not None:
            local_dt = event.end_datetime.astimezone(event_tz)
            local_dt = local_dt.replace(
                hour=new_end_datetime.hour,
                minute=new_end_datetime.minute,
                second=new_end_datetime.second,
                microsecond=new_end_datetime.microsecond,
            )
            event.end_datetime = local_dt

        for field, value in data.items():
            if field not in ["start_datetime", "end_datetime"]:
                setattr(event, field, value)

        event.save()

        if staff is not None:
            event.staff.set(staff)

    def _perform_single_update(self, event: "Event", **data) -> tuple["Event", int]:
        with transaction.atomic():
            staff = data.pop("staff", None)

            for field, value in data.items():
                setattr(event, field, value)

            event.save()

            if staff is not None:
                event.staff.set(staff)

            return event, 1

    def _perform_this_and_future_update(
        self, event: "Event", **data
    ) -> tuple["Event", int]:
        from ....models import Event

        original_start_datetime = Event.objects.get(pk=event.pk).start_datetime

        with transaction.atomic():
            template = (
                event if event.is_recurrence_template else event.recurrence_template
            )

            future_events = Event.objects.filter(
                recurrence_template=template,
                is_recurrence_template=False,
                start_datetime__gte=original_start_datetime,
            ).order_by("start_datetime")

            staff = data.pop("staff", None)
            new_start_datetime, new_end_datetime = self._extract_times_from_data(
                event, data
            )

            events_updated = 0
            for future_event in future_events:
                self._apply_updates_to_event(
                    future_event, data, new_start_datetime, new_end_datetime, staff
                )
                events_updated += 1

            # Propagate to template so future generated events inherit changes
            self._apply_updates_to_event(
                template, data, new_start_datetime, new_end_datetime, staff
            )

            return event, events_updated

    def _perform_all_in_series_update(
        self, event: "Event", **data
    ) -> tuple["Event", int]:
        from ....models import Event

        with transaction.atomic():
            template = (
                event if event.is_recurrence_template else event.recurrence_template
            )

            series_events = Event.objects.filter(
                recurrence_template=template,
                is_recurrence_template=False,
            ).order_by("start_datetime")

            staff = data.pop("staff", None)
            new_start_datetime, new_end_datetime = self._extract_times_from_data(
                event, data
            )

            events_updated = 0
            for series_event in series_events:
                self._apply_updates_to_event(
                    series_event, data, new_start_datetime, new_end_datetime, staff
                )
                events_updated += 1

            # Propagate to template so future generated events inherit changes
            self._apply_updates_to_event(
                template, data, new_start_datetime, new_end_datetime, staff
            )

            event.refresh_from_db()
            return event, events_updated

    # ------------------------------------------------------------------
    # Conflict validation helpers
    # ------------------------------------------------------------------

    def _validate_single_update_conflict(
        self, event: "Event", start_datetime, end_datetime, space
    ) -> ValidationResult:
        """Check a single event update for space-time conflicts."""
        from ....models import Event

        result = ValidationResult()

        conflicting_events = Event.objects.filter(
            space=space,
            start_datetime__lt=end_datetime,
            end_datetime__gt=start_datetime,
            is_recurrence_template=False,
        ).exclude(pk=event.pk)

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

        return result

    def _validate_bulk_update_conflicts(
        self, event: "Event", data: dict, events_to_update, space
    ) -> ValidationResult:
        """Check a bulk series update for space-time and staff conflicts."""
        from ....models import Event

        result = ValidationResult()

        new_start_datetime, new_end_datetime = self._extract_times_from_data(
            event, data
        )
        events_to_update_ids = list(events_to_update.values_list("pk", flat=True))

        for future_event in events_to_update:
            event_tz = future_event.space.location.timezone

            if new_start_datetime is not None:
                local_dt = future_event.start_datetime.astimezone(event_tz)
                updated_start_datetime = local_dt.replace(
                    hour=new_start_datetime.hour,
                    minute=new_start_datetime.minute,
                    second=new_start_datetime.second,
                    microsecond=new_start_datetime.microsecond,
                )
            else:
                updated_start_datetime = future_event.start_datetime

            if new_end_datetime is not None:
                local_dt = future_event.end_datetime.astimezone(event_tz)
                updated_end_datetime = local_dt.replace(
                    hour=new_end_datetime.hour,
                    minute=new_end_datetime.minute,
                    second=new_end_datetime.second,
                    microsecond=new_end_datetime.microsecond,
                )
            else:
                updated_end_datetime = future_event.end_datetime

            updated_space = data.get("space", future_event.space)

            # Space-time conflicts
            conflicting_events = Event.objects.filter(
                space=updated_space,
                start_datetime__lt=updated_end_datetime,
                end_datetime__gt=updated_start_datetime,
                is_recurrence_template=False,
            ).exclude(pk__in=events_to_update_ids)

            if conflicting_events.exists():
                conflict = conflicting_events.first()
                conflict_start_local = conflict.start_datetime.astimezone(event_tz)
                conflict_end_local = conflict.end_datetime.astimezone(event_tz)
                future_event_start_local = updated_start_datetime.astimezone(event_tz)
                result.add_warning(
                    f"Updating this series would create a conflict. "
                    f"Event on {future_event_start_local.strftime('%Y-%m-%d')} "
                    f"would conflict with: {conflict.service.name} "
                    f"({conflict_start_local.strftime('%Y-%m-%d %H:%M')} - "
                    f"{conflict_end_local.strftime('%H:%M')}) in {updated_space.name}.",
                    field="__all__",
                )
                # One warning is enough to flag the issue — no need to check
                # every single event in the series.
                break

            # Staff conflicts
            staff_members = data.get("staff", future_event.staff.all())
            if staff_members:
                staff_ids = [s.pk if hasattr(s, "pk") else s for s in staff_members]

                staff_conflicts = (
                    Event.objects.filter(
                        staff__id__in=staff_ids,
                        start_datetime__lt=updated_end_datetime,
                        end_datetime__gt=updated_start_datetime,
                    )
                    .exclude(pk__in=events_to_update_ids)
                    .prefetch_related("staff", "space__location")
                )

                if staff_conflicts.exists():
                    conflict = staff_conflicts.first()
                    conflicting_staff = conflict.staff.filter(id__in=staff_ids).first()
                    conflict_start_local = conflict.start_datetime.astimezone(event_tz)
                    conflict_end_local = conflict.end_datetime.astimezone(event_tz)
                    future_event_start_local = updated_start_datetime.astimezone(
                        event_tz
                    )
                    result.add_warning(
                        f"Updating this series would create a staff conflict. "
                        f"Event on {future_event_start_local.strftime('%Y-%m-%d')}: "
                        f"'{conflicting_staff.user.get_full_name()}' is already "
                        f"assigned to {conflict.service.name} "
                        f"({conflict_start_local.strftime('%Y-%m-%d %H:%M')} - "
                        f"{conflict_end_local.strftime('%H:%M')}) "
                        f"in {conflict.space.name}.",
                        field="staff",
                    )
                    break

        return result
