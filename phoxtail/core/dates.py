from datetime import date, datetime, timedelta

from babel import Locale, UnknownLocaleError
from babel.dates import format_date, format_interval, format_skeleton
from django.conf import settings
from django.utils import translation


def active_locale():
    """The Babel locale of Django's active language, for writing dates in it.

    With no request, or a language Babel has no data for, the site's default.
    """
    try:
        return Locale.parse(translation.to_locale(translation.get_language() or settings.LANGUAGE_CODE))
    except (UnknownLocaleError, ValueError):
        return Locale.parse(translation.to_locale(settings.LANGUAGE_CODE))


def iso_date(value):
    """A date, or a date already written "2026-10-04", as "2026-10-04"; anything else as "".

    A date and time counts as its date, as a date box shows it.
    """
    if isinstance(value, datetime):
        value = value.date()
    if isinstance(value, date):
        return value.isoformat()
    try:
        return date.fromisoformat(str(value or "")).isoformat()
    except ValueError:
        return ""


def display_date(value):
    """A date written for people, in the page's language: its weekday, day,
    month and year ("Mon, Oct 5, 2026"); ``iso_date`` writes one for machines.

    A date and time counts as its date: turn it to the zone it should be read
    in first.
    """
    if isinstance(value, datetime):
        value = value.date()
    return format_skeleton("yMMMEd", value, locale=active_locale())


def week_days(first, selected="", today=""):
    """The seven days from ``first``, written in the page's language.

    Each day: its value, its weekday, day and month as three short words
    ("Mon", "4", "Oct"), and whether it is the chosen day or today
    (``selected`` and ``today``: dates, or written "2026-10-05").
    """
    selected, today = iso_date(selected), iso_date(today)
    locale = active_locale()
    days = []
    for offset in range(7):
        day = first + timedelta(days=offset)
        days.append(
            {
                "value": day.isoformat(),
                "weekday": format_date(day, "EEE", locale=locale),
                "day": format_date(day, "d", locale=locale),
                "month": format_date(day, "LLL", locale=locale),
                "is_selected": day.isoformat() == selected,
                "is_today": day.isoformat() == today,
            }
        )
    return days


def week_range(first):
    """The seven days from ``first``, in the page's language: its month, or
    both for a week that crosses into the next, and its days, {"months":
    ["Oct"], "days": "11–17"} or {"months": ["Oct", "Nov"], "days": "26–1"};
    and "text", the range as one phrase ("Oct 26 – Nov 1"), for a reader that
    cannot see the two lines.
    """
    last = first + timedelta(days=6)
    locale = active_locale()
    ends = [first] if first.month == last.month else [first, last]
    return {
        "months": [format_date(day, "LLL", locale=locale) for day in ends],
        "days": format_interval(first, last, "d", locale=locale),
        "text": format_interval(first, last, "MMMd", locale=locale),
    }
