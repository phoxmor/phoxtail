import django.core.validators
import django.db.models.deletion
import modelcluster.fields
import modelsearch.index
import phoxtail.core.mixins
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("phoxtail_booking_core", "0001_initial"),
        ("phoxtail_booking_services", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Event",
            fields=[
                (
                    "id",
                    models.BigAutoField(primary_key=True, serialize=False),
                ),
                (
                    "uuid",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, unique=True
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True, null=True),
                ),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "recurrence_freq",
                    models.IntegerField(
                        blank=True,
                        choices=[(3, "Day"), (2, "Week"), (1, "Month"), (0, "Year")],
                        help_text="Frequency of recurrence",
                        null=True,
                        verbose_name="Frequency",
                    ),
                ),
                (
                    "recurrence_interval",
                    models.PositiveIntegerField(
                        default=1,
                        help_text="Interval between iterations (e.g., 2 for bi-weekly)",
                        validators=[django.core.validators.MinValueValidator(1)],
                        verbose_name="Interval",
                    ),
                ),
                (
                    "recurrence_byweekday",
                    models.JSONField(
                        blank=True,
                        default=list,
                        help_text="Which days of the week to repeat on (0=Monday, 1=Tuesday, 2=Wednesday, 3=Thursday, 4=Friday, 5=Saturday, 6=Sunday)",
                        verbose_name="Weekdays",
                    ),
                ),
                (
                    "recurrence_bymonthday",
                    models.IntegerField(
                        blank=True,
                        choices=[
                            (1, "Day 1"), (2, "Day 2"), (3, "Day 3"), (4, "Day 4"),
                            (5, "Day 5"), (6, "Day 6"), (7, "Day 7"), (8, "Day 8"),
                            (9, "Day 9"), (10, "Day 10"), (11, "Day 11"), (12, "Day 12"),
                            (13, "Day 13"), (14, "Day 14"), (15, "Day 15"), (16, "Day 16"),
                            (17, "Day 17"), (18, "Day 18"), (19, "Day 19"), (20, "Day 20"),
                            (21, "Day 21"), (22, "Day 22"), (23, "Day 23"), (24, "Day 24"),
                            (25, "Day 25"), (26, "Day 26"), (27, "Day 27"), (28, "Day 28"),
                            (29, "Day 29"), (30, "Day 30"), (31, "Day 31"), (-1, "Last Day"),
                        ],
                        help_text="Specific day of the month (1-31 or -1 for last day of month)",
                        null=True,
                        verbose_name="Day of month",
                    ),
                ),
                (
                    "recurrence_bysetpos",
                    models.IntegerField(
                        blank=True,
                        choices=[
                            (1, "First"), (2, "Second"), (3, "Third"),
                            (4, "Fourth"), (-1, "Last"),
                        ],
                        help_text="Position of the weekday in the month (e.g., 'First Monday')",
                        null=True,
                        verbose_name="Position",
                    ),
                ),
                (
                    "recurrence_byweekday_monthly",
                    models.IntegerField(
                        blank=True,
                        choices=[
                            (0, "Monday"), (1, "Tuesday"), (2, "Wednesday"),
                            (3, "Thursday"), (4, "Friday"), (5, "Saturday"),
                            (6, "Sunday"),
                        ],
                        help_text="Which weekday to use with position (e.g., 'Monday' in 'First Monday')",
                        null=True,
                        verbose_name="Weekday for monthly recurrence",
                    ),
                ),
                (
                    "recurrence_until",
                    models.DateTimeField(
                        blank=True,
                        help_text="Stop generating recurring events after this date/time",
                        null=True,
                        verbose_name="Recurrence end",
                    ),
                ),
                (
                    "recurrence_source_date",
                    models.DateField(
                        blank=True,
                        help_text="The date from the recurrence pattern this instance covers. Set once at creation; not updated when the event is moved.",
                        null=True,
                        verbose_name="Original occurrence date",
                    ),
                ),
                (
                    "is_recurrence_template",
                    models.BooleanField(
                        default=False,
                        help_text="True if this is a template instance (not a real occurrence)",
                        verbose_name="Is Template",
                    ),
                ),
                (
                    "recurrence_excluded_dates",
                    models.JSONField(
                        blank=True,
                        default=list,
                        help_text="Dates to skip during recurrence generation and projection. Populated automatically when a single occurrence is deleted.",
                        verbose_name="Excluded dates",
                    ),
                ),
                (
                    "start_datetime",
                    models.DateTimeField(
                        help_text="The exact date and time this event begins."
                    ),
                ),
                (
                    "end_datetime",
                    models.DateTimeField(
                        help_text="The exact date and time this event ends."
                    ),
                ),
                (
                    "capacity",
                    models.PositiveIntegerField(
                        help_text="Maximum number of participants allowed for this specific event."
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("CONFIRMED", "Confirmed"),
                            ("CANCELLED", "Cancelled"),
                            ("UNPUBLISHED", "Unpublished"),
                        ],
                        default="CONFIRMED",
                        help_text="Current status of the event (e.g., Confirmed, Cancelled, Unpublished).",
                        max_length=20,
                    ),
                ),
                (
                    "notes",
                    models.TextField(
                        blank=True,
                        help_text="Any specific notes for this event (e.g., 'Sub for John', 'Special workshop').",
                    ),
                ),
                (
                    "group",
                    models.ForeignKey(
                        blank=True,
                        help_text="Booking group membership required to book this event. If empty, anyone can book.",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="events",
                        to="phoxtail_booking_core.bookinggroup",
                    ),
                ),
                (
                    "recurrence_template",
                    models.ForeignKey(
                        blank=True,
                        help_text="Template instance that defines this recurring series",
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="series_instances",
                        to="phoxtail_booking_events.event",
                        verbose_name="Template",
                    ),
                ),
                (
                    "service",
                    models.ForeignKey(
                        help_text="The specific service offering for this event.",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="events",
                        to="phoxtail_booking_services.service",
                    ),
                ),
                (
                    "space",
                    models.ForeignKey(
                        help_text="The physical space where this event takes place.",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="events",
                        to="phoxtail_booking_core.space",
                    ),
                ),
                (
                    "staff",
                    models.ManyToManyField(
                        blank=True,
                        help_text="The staff members who are participating in or leading this event.",
                        related_name="events",
                        to="phoxtail_booking_core.staff",
                    ),
                ),
            ],
            options={
                "verbose_name": "Event",
                "verbose_name_plural": "Events",
                "ordering": ["start_datetime"],
            },
            bases=(
                phoxtail.core.mixins.AdminURLMixin,
                modelsearch.index.Indexed,
                models.Model,
            ),
        ),
        migrations.CreateModel(
            name="EventGenerationSchedule",
            fields=[
                (
                    "id",
                    models.BigAutoField(primary_key=True, serialize=False),
                ),
                (
                    "uuid",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, unique=True
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True, null=True),
                ),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "days_ahead",
                    models.PositiveIntegerField(
                        default=7,
                        help_text="How many days ahead to generate events (e.g., 7, 14, 30).",
                    ),
                ),
                (
                    "start_time",
                    models.TimeField(
                        default="02:00",
                        help_text="The time of day (hour and minute) when event generation should run in the location's timezone.",
                    ),
                ),
                (
                    "is_enabled",
                    models.BooleanField(
                        default=True,
                        help_text="Whether this schedule is currently active. Disabled schedules will not generate events.",
                    ),
                ),
                (
                    "location",
                    models.ForeignKey(
                        help_text="The location for which events will be generated.",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="event_generation_schedules",
                        to="phoxtail_booking_core.location",
                    ),
                ),
            ],
            options={
                "verbose_name": "Event Generation Schedule",
                "verbose_name_plural": "Event Generation Schedules",
                "ordering": ["location__name"],
                "unique_together": {("location",)},
            },
            bases=(
                phoxtail.core.mixins.AdminURLMixin,
                modelsearch.index.Indexed,
                models.Model,
            ),
        ),
        migrations.CreateModel(
            name="EventGenerationScheduleExclusion",
            fields=[
                (
                    "id",
                    models.BigAutoField(primary_key=True, serialize=False),
                ),
                (
                    "uuid",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, unique=True
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True, null=True),
                ),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "name",
                    models.CharField(
                        help_text="A descriptive name for this exclusion (e.g. 'Public Holidays 2026').",
                        max_length=255,
                    ),
                ),
                (
                    "schedule",
                    models.ForeignKey(
                        help_text="The generation schedule this exclusion applies to.",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="exclusions",
                        to="phoxtail_booking_events.eventgenerationschedule",
                    ),
                ),
            ],
            options={
                "verbose_name": "Event Generation Schedule Exclusion",
                "verbose_name_plural": "Event Generation Schedule Exclusions",
                "ordering": ["schedule__location__name", "name"],
            },
            bases=(
                phoxtail.core.mixins.AdminURLMixin,
                modelsearch.index.Indexed,
                models.Model,
            ),
        ),
        migrations.CreateModel(
            name="EventGenerationScheduleExclusionPeriod",
            fields=[
                (
                    "id",
                    models.BigAutoField(primary_key=True, serialize=False),
                ),
                (
                    "uuid",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, unique=True
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True, null=True),
                ),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "start_date",
                    models.DateField(
                        help_text="Start date of the exclusion period (inclusive).",
                    ),
                ),
                (
                    "end_date",
                    models.DateField(
                        blank=True,
                        help_text="End date of the exclusion period (inclusive). Leave empty to exclude only the start date.",
                        null=True,
                    ),
                ),
                (
                    "exclusion",
                    modelcluster.fields.ParentalKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="periods",
                        to="phoxtail_booking_events.eventgenerationscheduleexclusion",
                    ),
                ),
            ],
            options={
                "verbose_name": "Exclusion Period",
                "verbose_name_plural": "Exclusion Periods",
                "ordering": ["start_date"],
            },
        ),
    ]
