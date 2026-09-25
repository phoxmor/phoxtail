"""A time given for a place is read on its local clocks.

Whoever gives a time for something at a place means the place's time.
:func:`localize` turns such a value — as it arrives over an API, say — into
the instant it names, and refuses what does not name exactly one, as pytz's
``localize(..., is_dst=None)`` once did:

- a time given without an offset is read on the zone's clocks, but refused
  when those clocks skip it or show it twice (the nights daylight saving
  starts and ends);
- a time given with an offset is kept only when the offset is the zone's at
  that moment — a different one means the sender converted, or meant another
  place, and the time cannot be trusted.

The refusals are ``ValidationError``, which the API answers with 422.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, tzinfo

from django.core.exceptions import ValidationError
from django.utils import timezone


def localize(value: datetime, zone: tzinfo) -> datetime:
    """The instant *value* names on *zone*'s clocks, or ``ValidationError``."""
    # Through UTC throughout, since astimezone() returns a value already in the
    # zone unchanged — its own offset would always seem to match.
    if timezone.is_aware(value):
        expected = value.astimezone(UTC).astimezone(zone).utcoffset()
        if value.utcoffset() != expected:
            raise ValidationError(
                "%(value)s is not a time on %(zone)s clocks, which are at %(expected)s then; "
                "send it without an offset or with %(expected)s.",
                code="offset_mismatch",
                params={"value": value.isoformat(), "zone": zone, "expected": _offset(expected)},
            )
        return value

    first = value.replace(tzinfo=zone, fold=0)
    second = value.replace(tzinfo=zone, fold=1)
    if first.utcoffset() == second.utcoffset():
        return first
    # A skipped time comes back from UTC as another wall-clock time; a repeated one as itself.
    if first.astimezone(UTC).astimezone(zone).replace(tzinfo=None) != value:
        raise ValidationError(
            "%(value)s does not exist on %(zone)s clocks; they skip it that night.",
            code="nonexistent_time",
            params={"value": value.isoformat(), "zone": zone},
        )
    raise ValidationError(
        "%(value)s happens twice on %(zone)s clocks; send it with %(first)s or %(second)s.",
        code="ambiguous_time",
        params={
            "value": value.isoformat(),
            "zone": zone,
            "first": _offset(first.utcoffset()),
            "second": _offset(second.utcoffset()),
        },
    )


def _offset(delta: timedelta | None) -> str:
    """``+02:00`` for a UTC offset."""
    minutes = int((delta or timedelta()).total_seconds()) // 60
    sign = "+" if minutes >= 0 else "-"
    return f"{sign}{abs(minutes) // 60:02d}:{abs(minutes) % 60:02d}"
