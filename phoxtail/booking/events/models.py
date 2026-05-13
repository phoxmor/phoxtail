from django import forms
from django.contrib.auth import get_user_model
from django.db import models
from django.db.models.signals import pre_delete
from django.dispatch import receiver
from django.utils.translation import gettext_lazy as _
from modelcluster.fields import ParentalKey
from modelcluster.models import ClusterableModel
from wagtail.admin.panels import FieldPanel, InlinePanel
from wagtail.admin.panels.group import ObjectList, TabbedInterface
from wagtail.search import index

from phoxtail.booking.core.models import BookingGroup, Location, Space, Staff
from phoxtail.booking.services.models import Service
from phoxtail.core.mixins import AdminURLMixin, TimestampMixin, UUIDMixin

from .constants import EventStatus
from .managers import EventManager
from .mixins import RecurrenceMixin

User = get_user_model()


class Event(
    UUIDMixin,
    TimestampMixin,
    AdminURLMixin,
    RecurrenceMixin,
    index.Indexed,
    models.Model,
):
    """
    Represents a specific, scheduled instance of a Service. This is what
    users will actually reserve a spot in.
    """

    service = models.ForeignKey(
        Service,
        on_delete=models.CASCADE,
        related_name="events",
        help_text="The specific service offering for this event.",
    )
    start_datetime = models.DateTimeField(help_text="The exact date and time this event begins.")
    end_datetime = models.DateTimeField(help_text="The exact date and time this event ends.")
    space = models.ForeignKey(
        Space,
        on_delete=models.PROTECT,
        related_name="events",
        help_text="The physical space where this event takes place.",
    )
    staff = models.ManyToManyField(
        Staff,
        related_name="events",
        blank=True,
        help_text="The staff members who are participating in or leading this event.",
    )
    capacity = models.PositiveIntegerField(help_text="Maximum number of participants allowed for this specific event.")
    group = models.ForeignKey(
        BookingGroup,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="events",
        help_text="Booking group membership required to book this event. If empty, anyone can book.",
    )
    status = models.CharField(
        max_length=20,
        choices=EventStatus.choices,
        default=EventStatus.CONFIRMED,
        help_text="Current status of the event (e.g., Confirmed, Cancelled, Unpublished).",
    )
    notes = models.TextField(
        blank=True,
        help_text="Any specific notes for this event (e.g., 'Sub for John', 'Special workshop').",
    )

    objects = EventManager()

    details_panels = [
        FieldPanel("service"),
        FieldPanel("start_datetime"),
        FieldPanel("end_datetime"),
        FieldPanel("space"),
        FieldPanel(
            "staff",
            widget=forms.CheckboxSelectMultiple,
        ),
        FieldPanel("capacity"),
        FieldPanel("group"),
        FieldPanel("status"),
        FieldPanel("notes"),
    ]

    edit_handler = TabbedInterface(
        [
            ObjectList(details_panels, heading="Details"),
            ObjectList(RecurrenceMixin.recurrence_panels, heading="Recurrence"),
        ]
    )

    search_fields = [
        index.FilterField("id"),
        index.AutocompleteField("id"),
        index.FilterField("uuid"),
        index.AutocompleteField("uuid"),
        index.RelatedFields(
            "service",
            [
                index.AutocompleteField("name"),
            ],
        ),
        index.SearchField("notes"),
        index.FilterField("service"),
        index.FilterField("space"),
        index.FilterField("staff"),
        index.FilterField("group"),
        index.FilterField("status"),
        index.FilterField("start_datetime"),
        index.AutocompleteField("start_datetime"),
    ]

    class Meta:
        verbose_name = "Event"
        verbose_name_plural = "Events"
        ordering = ["start_datetime"]

    def __str__(self):
        location = getattr(self.space, "location", None)
        if location:
            dt = self.start_datetime.astimezone(location.timezone).strftime("%Y-%m-%d %H:%M %Z")
            return f"{self.service.name} at {dt}"

        return f"{self.service.name} at {self.start_datetime.strftime('%Y-%m-%d %H:%M %Z')}"

    @property
    def is_cancelled(self) -> bool:
        """Check if the event is cancelled based on status."""
        return self.event_service.is_cancelled()

    @property
    def is_unpublished(self) -> bool:
        """Check if the event is unpublished based on status."""
        return self.event_service.is_unpublished()

    @property
    def event_service(self):
        """Access to EventService for business logic."""
        from .services import EventService

        return EventService(self)

    def generate_recurring_events(self, days_ahead=7):
        """Generate recurring event instances. Delegates to EventService."""
        return self.event_service.generate_recurring_events(days_ahead)

    def user_can_access_event(self, user: User) -> bool:
        return self.event_service.user_can_access_event(user)

    @property
    def reserved_spots_count(self) -> int:
        """Number of reserved spots (confirmed + completed reservations)."""
        return self.event_service.get_reserved_spots_count()

    @property
    def is_full(self) -> bool:
        """Check if the event is at capacity."""
        return self.event_service.get_is_full()

    @property
    def short_series_id(self):
        """Short version of series identifier (first 8 chars)."""
        return self.event_service.get_short_series_id()

    def save(self, *args, **kwargs):
        # Set initial capacity from space if new event and capacity not set
        is_new = not self.pk
        if is_new and self.capacity is None and self.space:
            self.capacity = self.space.capacity

        super().save(*args, **kwargs)


class EventGenerationSchedule(
    UUIDMixin,
    TimestampMixin,
    AdminURLMixin,
    index.Indexed,
    models.Model,
):
    """
    Defines when and how recurring events should be automatically generated
    for a specific location. Each schedule creates a Celery Beat periodic task
    that runs at the specified time in the location's timezone.
    """

    location = models.ForeignKey(
        Location,
        on_delete=models.CASCADE,
        related_name="event_generation_schedules",
        help_text="The location for which events will be generated.",
    )
    days_ahead = models.PositiveIntegerField(
        default=7,
        help_text="How many days ahead to generate events (e.g., 7, 14, 30).",
    )
    start_time = models.TimeField(
        default="02:00",
        help_text="The time of day (hour and minute) when event generation should run in the location's timezone.",
    )
    is_enabled = models.BooleanField(
        default=True,
        help_text="Whether this schedule is currently active. Disabled schedules will not generate events.",
    )

    panels = [
        FieldPanel("location"),
        FieldPanel("days_ahead"),
        FieldPanel("start_time"),
        FieldPanel("is_enabled"),
    ]

    search_fields = [
        index.RelatedFields(
            "location",
            [
                index.AutocompleteField("name"),
            ],
        ),
        index.FilterField("location"),
        index.FilterField("is_enabled"),
    ]

    class Meta:
        verbose_name = _("Event Generation Schedule")
        verbose_name_plural = _("Event Generation Schedules")
        ordering = ["location__name"]
        unique_together = [["location"]]

    def __str__(self):
        status = "Enabled" if self.is_enabled else "Disabled"
        return f"{self.location.name} - {self.days_ahead} days ahead at {self.start_time.strftime('%H:%M')} ({status})"

    def save(self, *args, **kwargs):
        """Save the schedule and sync with django-celery-beat."""
        super().save(*args, **kwargs)
        self.sync_to_periodic_task()

    def delete(self, *args, **kwargs):
        """Delete the schedule and its associated periodic task."""
        self.delete_periodic_task()
        super().delete(*args, **kwargs)

    def sync_to_periodic_task(self):
        """
        Create or update a django-celery-beat PeriodicTask for this schedule.
        The task will run at the specified time in the location's timezone.
        """
        import json

        from django.db import OperationalError, ProgrammingError
        from django_celery_beat.models import CrontabSchedule, PeriodicTask

        try:
            # Generate unique task name based on location
            task_name = f"generate_events_{self.location.slug}"

            # Create or get crontab schedule (hour and minute in location's timezone)
            crontab, _ = CrontabSchedule.objects.get_or_create(
                minute=self.start_time.minute,
                hour=self.start_time.hour,
                day_of_week="*",  # Every day
                day_of_month="*",
                month_of_year="*",
                timezone=self.location.timezone,
            )

            # Task arguments
            task_kwargs = {
                "days_ahead": self.days_ahead,
                "location_id": str(self.location.id),
            }

            # Create or update periodic task
            periodic_task, _ = PeriodicTask.objects.update_or_create(
                name=task_name,
                defaults={
                    "crontab": crontab,
                    "task": "phoxtail.booking.events.tasks.generate_recurring_events_task",
                    "kwargs": json.dumps(task_kwargs),
                    "enabled": self.is_enabled,
                },
            )
            return periodic_task
        except (ProgrammingError, OperationalError):
            # Database tables not ready yet
            return None

    def delete_periodic_task(self):
        """Delete the associated periodic task if it exists."""
        from django.db import OperationalError, ProgrammingError
        from django_celery_beat.models import PeriodicTask

        task_name = f"generate_events_{self.location.slug}"

        try:
            periodic_task = PeriodicTask.objects.get(name=task_name)
            periodic_task.delete()
        except (PeriodicTask.DoesNotExist, ProgrammingError, OperationalError):
            pass


class EventGenerationScheduleExclusion(
    UUIDMixin,
    TimestampMixin,
    AdminURLMixin,
    index.Indexed,
    ClusterableModel,
):
    """
    A named exclusion rule for event generation. Groups one or more date
    periods during which no events should be generated for the associated
    schedule's location (e.g. "Summer Holiday 2026", "Public Holidays").

    Periods are managed as inline children via EventGenerationScheduleExclusionPeriod.
    """

    schedule = models.ForeignKey(
        EventGenerationSchedule,
        on_delete=models.CASCADE,
        related_name="exclusions",
        help_text=_("The generation schedule this exclusion applies to."),
    )
    name = models.CharField(
        max_length=255,
        help_text=_("A descriptive name for this exclusion (e.g. 'Public Holidays 2026')."),
    )

    panels = [
        FieldPanel("schedule"),
        FieldPanel("name"),
        InlinePanel("periods", label=_("Exclusion periods")),
    ]

    search_fields = [
        index.AutocompleteField("name"),
        index.SearchField("name"),
        index.FilterField("schedule"),
    ]

    class Meta:
        verbose_name = _("Event Generation Schedule Exclusion")
        verbose_name_plural = _("Event Generation Schedule Exclusions")
        ordering = ["schedule__location__name", "name"]

    def __str__(self):
        return f"{self.name} ({self.schedule.location.name})"


class EventGenerationScheduleExclusionPeriod(
    UUIDMixin,
    TimestampMixin,
    models.Model,
):
    """
    A single date or date range within an EventGenerationScheduleExclusion.

    If only start_date is provided, the exclusion applies to that single day.
    If both start_date and end_date are provided, the exclusion covers the
    entire range (inclusive).
    """

    exclusion = ParentalKey(
        EventGenerationScheduleExclusion,
        on_delete=models.CASCADE,
        related_name="periods",
    )
    start_date = models.DateField(
        help_text=_("Start date of the exclusion period (inclusive)."),
    )
    end_date = models.DateField(
        null=True,
        blank=True,
        help_text=_("End date of the exclusion period (inclusive). Leave empty to exclude only the start date."),
    )

    panels = [
        FieldPanel("start_date"),
        FieldPanel("end_date"),
    ]

    class Meta:
        verbose_name = _("Exclusion Period")
        verbose_name_plural = _("Exclusion Periods")
        ordering = ["start_date"]

    def __str__(self):
        if self.end_date:
            return f"{self.start_date} — {self.end_date}"
        return str(self.start_date)

    def contains_date(self, date):
        """Check if a given date falls within this exclusion period."""
        if self.end_date:
            return self.start_date <= date <= self.end_date
        return date == self.start_date


# Signal handlers
@receiver(pre_delete, sender=EventGenerationSchedule)
def cleanup_periodic_task_on_delete(sender, instance, **kwargs):
    """
    Delete associated PeriodicTask when EventGenerationSchedule is deleted.

    This ensures cleanup happens even during bulk deletes from admin,
    which bypass the model's delete() method.
    """
    instance.delete_periodic_task()
