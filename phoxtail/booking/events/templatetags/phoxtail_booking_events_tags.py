from collections import defaultdict
from datetime import timedelta

from django import template

register = template.Library()


@register.simple_tag
def get_weekly_schedule(location):
    """
    Build a weekly schedule grid for the current week at a given location.

    Returns a dict with:
      - week_structure: list of 7 day dicts, each with date, weekday, day_display,
        is_today, and hours (list of hour slots with events)
      - time_slots: list of hour dicts that have at least one event

    Only confirmed, live events are included. Recurring event projections are
    generated via EventService so template-based recurrences appear correctly.
    """
    if not location:
        return {"week_structure": [], "time_slots": []}

    from django.utils import timezone

    from phoxtail.booking.events.constants import EventStatus
    from phoxtail.booking.events.models import Event
    from phoxtail.booking.events.services import EventService

    today = timezone.now().astimezone(location.timezone).date()
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)
    week_days = [week_start + timedelta(days=i) for i in range(7)]

    queryset = Event.objects.filter(
        space__location=location,
        status=EventStatus.CONFIRMED,
        is_recurrence_template=False,
    ).select_related(
        "space",
        "space__location",
        "service",
        "service__palette",
    )

    all_events = EventService.get_events_with_recurrence_projections(
        queryset=queryset,
        start_date=week_start,
        end_date=week_end,
    )

    events_by_day = defaultdict(list)
    events_by_day_and_hour = defaultdict(lambda: defaultdict(list))

    for event in all_events:
        loc_tz = event.space.location.timezone
        local_start = event.start_datetime.astimezone(loc_tz)
        event_date = local_start.date()
        start_hour = local_start.hour
        events_by_day[event_date].append(event)
        events_by_day_and_hour[event_date][start_hour].append(
            {"event": event, "start_hour": start_hour}
        )

    hours_with_events = set()
    for day_events in events_by_day_and_hour.values():
        hours_with_events.update(day_events.keys())

    if hours_with_events:
        earliest_hour = min(hours_with_events)
        latest_hour = max(hours_with_events)
    else:
        earliest_hour = 8
        latest_hour = 20

    time_slots = [
        {
            "hour": h,
            "display": f"{h:02d}:00",
        }
        for h in range(earliest_hour, latest_hour + 1)
        if h in hours_with_events
    ]

    week_structure = []
    for day in week_days:
        day_hours = [
            {
                "hour": ts["hour"],
                "display": ts["display"],
                "events": events_by_day_and_hour[day].get(ts["hour"], []),
            }
            for ts in time_slots
        ]
        week_structure.append(
            {
                "date": day,
                "weekday": day.strftime("%A"),
                "day_display": day.strftime("%b %d"),
                "is_today": day == today,
                "hours": day_hours,
            }
        )

    return {"week_structure": week_structure, "time_slots": time_slots}
