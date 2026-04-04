from typing import TYPE_CHECKING

from ..constants import EventStatus

if TYPE_CHECKING:
    from ..models import Event


class ProjectedEvent:
    """
    Represents a virtual/projected event that hasn't been created yet.
    Used for displaying recurring events before they're actually generated.
    """

    def __init__(self, template_event: "Event", start_datetime, end_datetime):
        self.id = None  # Virtual events don't have IDs
        self.service = template_event.service
        self.start_datetime = start_datetime
        self.end_datetime = end_datetime
        self.space = template_event.space
        self.staff = template_event.staff
        self.capacity = template_event.capacity
        self.group = template_event.group
        self.status = template_event.status
        self.notes = template_event.notes
        # Point recurrence_template directly to the source template event
        self.recurrence_template = template_event
        self.is_recurrence_template = False  # Projected events are never templates
        self.recurrence_freq = template_event.recurrence_freq
        self.recurrence_interval = template_event.recurrence_interval
        self.recurrence_byweekday = template_event.recurrence_byweekday
        self.recurrence_bymonthday = template_event.recurrence_bymonthday
        self.recurrence_bysetpos = template_event.recurrence_bysetpos
        self.recurrence_byweekday_monthly = template_event.recurrence_byweekday_monthly
        self.recurrence_until = template_event.recurrence_until
        self.is_projected = True  # Flag to identify virtual events

    @property
    def is_cancelled(self) -> bool:
        return self.status == EventStatus.CANCELLED

    @property
    def is_unpublished(self) -> bool:
        return self.status == EventStatus.UNPUBLISHED
