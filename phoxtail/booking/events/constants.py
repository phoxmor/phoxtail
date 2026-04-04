from dateutil import rrule
from django.db import models
from django.utils.translation import gettext_lazy as _


class EventStatus(models.TextChoices):
    """Choices for Event status"""

    CONFIRMED = "CONFIRMED", _("Confirmed")
    CANCELLED = "CANCELLED", _("Cancelled")
    UNPUBLISHED = "UNPUBLISHED", _("Unpublished")


class EventUpdateScope(models.TextChoices):
    """Choices for event series update scope"""

    THIS_EVENT_ONLY = "this_event_only", _("This event only")
    THIS_AND_FUTURE_EVENTS = "this_and_future_events", _("This and future events")
    ALL_EVENTS_IN_SERIES = "all_events_in_series", _("All events in series")


class RecurrenceFrequency(models.IntegerChoices):
    """Choices for recurrence frequency"""

    DAILY = rrule.DAILY, _("Day")
    WEEKLY = rrule.WEEKLY, _("Week")
    MONTHLY = rrule.MONTHLY, _("Month")
    YEARLY = rrule.YEARLY, _("Year")


class RecurrenceWeekday(models.IntegerChoices):
    """Choices for recurrence weekdays"""

    MONDAY = rrule.MO.weekday, _("Monday")
    TUESDAY = rrule.TU.weekday, _("Tuesday")
    WEDNESDAY = rrule.WE.weekday, _("Wednesday")
    THURSDAY = rrule.TH.weekday, _("Thursday")
    FRIDAY = rrule.FR.weekday, _("Friday")
    SATURDAY = rrule.SA.weekday, _("Saturday")
    SUNDAY = rrule.SU.weekday, _("Sunday")
