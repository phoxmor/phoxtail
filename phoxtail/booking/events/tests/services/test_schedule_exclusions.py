"""
Tests for EventGenerationScheduleExclusion — location-level date exclusions
that prevent event generation and projection on specified dates.
"""

import datetime
from datetime import time

import pytest
from django.utils import timezone
from freezegun import freeze_time

UTC = datetime.UTC

from phoxtail.booking.events.models import (
    Event,
    EventGenerationSchedule,
    EventGenerationScheduleExclusion,
    EventGenerationScheduleExclusionPeriod,
)
from phoxtail.booking.events.services import EventService

from ..factories import RecurringTemplateFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def schedule(location):
    return EventGenerationSchedule.objects.create(
        location=location,
        days_ahead=30,
        start_time=time(2, 0),
        is_enabled=True,
    )


@pytest.fixture
def exclusion(schedule):
    return EventGenerationScheduleExclusion.objects.create(
        schedule=schedule,
        name="Public Holidays 2024",
    )


# ---------------------------------------------------------------------------
# Model basics
# ---------------------------------------------------------------------------


class TestExclusionPeriodContainsDate:
    def test_single_date_match(self, exclusion):
        period = EventGenerationScheduleExclusionPeriod.objects.create(
            exclusion=exclusion,
            start_date=datetime.date(2024, 6, 10),
        )
        assert period.contains_date(datetime.date(2024, 6, 10))
        assert not period.contains_date(datetime.date(2024, 6, 11))

    def test_date_range_match(self, exclusion):
        period = EventGenerationScheduleExclusionPeriod.objects.create(
            exclusion=exclusion,
            start_date=datetime.date(2024, 6, 10),
            end_date=datetime.date(2024, 6, 14),
        )
        assert period.contains_date(datetime.date(2024, 6, 10))
        assert period.contains_date(datetime.date(2024, 6, 12))
        assert period.contains_date(datetime.date(2024, 6, 14))
        assert not period.contains_date(datetime.date(2024, 6, 9))
        assert not period.contains_date(datetime.date(2024, 6, 15))


# ---------------------------------------------------------------------------
# Generation skips excluded dates
# ---------------------------------------------------------------------------


class TestGenerationSkipsExcludedDates:
    @freeze_time("2024-06-03 08:00:00")
    def test_single_date_exclusion_skips_generation(self, service, space, schedule, exclusion):
        """A single-date exclusion should prevent event generation on that date."""
        EventGenerationScheduleExclusionPeriod.objects.create(
            exclusion=exclusion,
            start_date=datetime.date(2024, 6, 10),
        )

        template = RecurringTemplateFactory(
            service=service,
            space=space,
            start_datetime=timezone.make_aware(datetime.datetime(2024, 6, 3, 10, 0), UTC),
            end_datetime=timezone.make_aware(datetime.datetime(2024, 6, 3, 11, 0), UTC),
        )

        EventService(template).generate_recurring_events(days_ahead=30)

        generated_dates = list(
            Event.objects.filter(
                recurrence_template=template,
                is_recurrence_template=False,
            ).values_list("recurrence_source_date", flat=True)
        )
        assert datetime.date(2024, 6, 10) not in generated_dates
        # Other dates should still be generated
        assert datetime.date(2024, 6, 17) in generated_dates

    @freeze_time("2024-06-03 08:00:00")
    def test_date_range_exclusion_skips_generation(self, service, space, schedule, exclusion):
        """A date range exclusion should prevent generation for all dates in range."""
        EventGenerationScheduleExclusionPeriod.objects.create(
            exclusion=exclusion,
            start_date=datetime.date(2024, 6, 10),
            end_date=datetime.date(2024, 6, 17),
        )

        template = RecurringTemplateFactory(
            service=service,
            space=space,
            start_datetime=timezone.make_aware(datetime.datetime(2024, 6, 3, 10, 0), UTC),
            end_datetime=timezone.make_aware(datetime.datetime(2024, 6, 3, 11, 0), UTC),
        )

        EventService(template).generate_recurring_events(days_ahead=30)

        generated_dates = list(
            Event.objects.filter(
                recurrence_template=template,
                is_recurrence_template=False,
            ).values_list("recurrence_source_date", flat=True)
        )
        assert datetime.date(2024, 6, 10) not in generated_dates
        assert datetime.date(2024, 6, 17) not in generated_dates
        # Dates outside the range should still be generated
        assert datetime.date(2024, 6, 24) in generated_dates

    @freeze_time("2024-06-03 08:00:00")
    def test_exclusion_for_different_location_does_not_affect(self, service, space, location):
        """Exclusions on one location should not affect another location's events."""
        from phoxtail.booking.subscriptions.tests.factories import LocationFactory

        from ..factories import SpaceFactory

        other_location = LocationFactory(timezone="UTC")
        other_space = SpaceFactory(location=other_location)
        other_schedule = EventGenerationSchedule.objects.create(
            location=other_location,
            days_ahead=30,
            start_time=time(2, 0),
            is_enabled=True,
        )
        other_exclusion = EventGenerationScheduleExclusion.objects.create(
            schedule=other_schedule,
            name="Other Location Holiday",
        )
        EventGenerationScheduleExclusionPeriod.objects.create(
            exclusion=other_exclusion,
            start_date=datetime.date(2024, 6, 10),
        )

        # Template on the original location — should NOT be affected
        template = RecurringTemplateFactory(
            service=service,
            space=space,
            start_datetime=timezone.make_aware(datetime.datetime(2024, 6, 3, 10, 0), UTC),
            end_datetime=timezone.make_aware(datetime.datetime(2024, 6, 3, 11, 0), UTC),
        )

        EventService(template).generate_recurring_events(days_ahead=30)

        generated_dates = list(
            Event.objects.filter(
                recurrence_template=template,
                is_recurrence_template=False,
            ).values_list("recurrence_source_date", flat=True)
        )
        assert datetime.date(2024, 6, 10) in generated_dates


# ---------------------------------------------------------------------------
# Projection skips excluded dates
# ---------------------------------------------------------------------------


class TestProjectionSkipsExcludedDates:
    @freeze_time("2024-06-03 08:00:00")
    def test_single_date_exclusion_skips_projection(self, service, space, schedule, exclusion):
        """A single-date exclusion should prevent projection on that date."""
        EventGenerationScheduleExclusionPeriod.objects.create(
            exclusion=exclusion,
            start_date=datetime.date(2024, 6, 10),
        )

        RecurringTemplateFactory(
            service=service,
            space=space,
            start_datetime=timezone.make_aware(datetime.datetime(2024, 6, 3, 10, 0), UTC),
            end_datetime=timezone.make_aware(datetime.datetime(2024, 6, 3, 11, 0), UTC),
        )

        all_events = EventService.get_events_with_recurrence_projections(
            Event.objects.all(),
            start_date=datetime.date(2024, 6, 3),
            end_date=datetime.date(2024, 6, 17),
        )
        projected_dates = [e.start_datetime.date() for e in all_events if getattr(e, "is_projected", False)]
        assert datetime.date(2024, 6, 10) not in projected_dates

    @freeze_time("2024-06-03 08:00:00")
    def test_date_range_exclusion_skips_projection(self, service, space, schedule, exclusion):
        """A date range exclusion should prevent projection for all dates in range."""
        EventGenerationScheduleExclusionPeriod.objects.create(
            exclusion=exclusion,
            start_date=datetime.date(2024, 6, 10),
            end_date=datetime.date(2024, 6, 17),
        )

        RecurringTemplateFactory(
            service=service,
            space=space,
            start_datetime=timezone.make_aware(datetime.datetime(2024, 6, 3, 10, 0), UTC),
            end_datetime=timezone.make_aware(datetime.datetime(2024, 6, 3, 11, 0), UTC),
        )

        all_events = EventService.get_events_with_recurrence_projections(
            Event.objects.all(),
            start_date=datetime.date(2024, 6, 3),
            end_date=datetime.date(2024, 6, 24),
        )
        projected_dates = [e.start_datetime.date() for e in all_events if getattr(e, "is_projected", False)]
        assert datetime.date(2024, 6, 10) not in projected_dates
        assert datetime.date(2024, 6, 17) not in projected_dates
        # Dates outside range should still be projected
        assert datetime.date(2024, 6, 24) in projected_dates


# ---------------------------------------------------------------------------
# Multiple exclusions combine correctly
# ---------------------------------------------------------------------------


class TestMultipleExclusions:
    @freeze_time("2024-06-03 08:00:00")
    def test_multiple_exclusion_periods_all_respected(self, service, space, schedule, exclusion):
        """Multiple periods within the same exclusion should all be skipped."""
        EventGenerationScheduleExclusionPeriod.objects.create(
            exclusion=exclusion,
            start_date=datetime.date(2024, 6, 10),
        )
        EventGenerationScheduleExclusionPeriod.objects.create(
            exclusion=exclusion,
            start_date=datetime.date(2024, 6, 24),
        )

        template = RecurringTemplateFactory(
            service=service,
            space=space,
            start_datetime=timezone.make_aware(datetime.datetime(2024, 6, 3, 10, 0), UTC),
            end_datetime=timezone.make_aware(datetime.datetime(2024, 6, 3, 11, 0), UTC),
        )

        EventService(template).generate_recurring_events(days_ahead=30)

        generated_dates = list(
            Event.objects.filter(
                recurrence_template=template,
                is_recurrence_template=False,
            ).values_list("recurrence_source_date", flat=True)
        )
        assert datetime.date(2024, 6, 10) not in generated_dates
        assert datetime.date(2024, 6, 24) not in generated_dates
        assert datetime.date(2024, 6, 17) in generated_dates

    @freeze_time("2024-06-03 08:00:00")
    def test_multiple_exclusion_groups_all_respected(self, service, space, schedule):
        """Multiple named exclusions on the same schedule should all be respected."""
        holidays = EventGenerationScheduleExclusion.objects.create(
            schedule=schedule,
            name="Public Holidays",
        )
        EventGenerationScheduleExclusionPeriod.objects.create(
            exclusion=holidays,
            start_date=datetime.date(2024, 6, 10),
        )

        maintenance = EventGenerationScheduleExclusion.objects.create(
            schedule=schedule,
            name="Maintenance Window",
        )
        EventGenerationScheduleExclusionPeriod.objects.create(
            exclusion=maintenance,
            start_date=datetime.date(2024, 6, 24),
        )

        template = RecurringTemplateFactory(
            service=service,
            space=space,
            start_datetime=timezone.make_aware(datetime.datetime(2024, 6, 3, 10, 0), UTC),
            end_datetime=timezone.make_aware(datetime.datetime(2024, 6, 3, 11, 0), UTC),
        )

        EventService(template).generate_recurring_events(days_ahead=30)

        generated_dates = list(
            Event.objects.filter(
                recurrence_template=template,
                is_recurrence_template=False,
            ).values_list("recurrence_source_date", flat=True)
        )
        assert datetime.date(2024, 6, 10) not in generated_dates
        assert datetime.date(2024, 6, 24) not in generated_dates
