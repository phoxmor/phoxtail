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

A question asked in clock times — "what starts on Sunday", "what starts
after 18:00 on 1 Nov" — is asked of each row on its own clocks:
:func:`filter_on_local_clocks`. Django's ``__date`` and ``Trunc`` take one
zone per query; rows at places in different zones need one per row. Any other
condition that depends on the clocks — "ends today or later" — is asked the same
way: :func:`on_local_clocks`.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import UTC, date, datetime, timedelta, tzinfo
from zoneinfo import ZoneInfo

from django.core.exceptions import FieldDoesNotExist, ValidationError
from django.db.models import DateTimeField, Q, QuerySet
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


def filter_on_local_clocks(queryset: QuerySet, zone_path: str, zones: Iterable, **lookups) -> QuerySet:
    """*queryset* narrowed by *lookups*, each bare datetime in them read on the row's own clocks.

    *zone_path* leads from a row to the zone of its place, as a lookup path;
    *zones* are the zones rows can be at — every one of them, since a row in
    a zone left out is left out too, while a zone no row is at costs nothing.
    ``start_datetime__gte=datetime(2026, 11, 1)`` keeps the rows that start
    on or after midnight on 1 Nov where each row happens. Each zone turns the
    bound into one instant, so the database still compares instants, and can
    use an index on the column. A bound with an offset already names one
    instant and is compared as it is.

    A bound is where a range starts or stops, not a time someone booked, so a
    clock time the zone skips or repeats is not refused: a skipped one starts
    where the clocks resume, and a repeated one is its first showing — or, for
    an upper bound (``__lt``, ``__lte``), its second.
    """
    for lookup, value in lookups.items():
        _refuse_one_zone_readings(queryset.model, lookup, value)
        if isinstance(value, (list, tuple, set)) and any(_is_clock_time(item) for item in value):
            raise TypeError(
                f"{lookup}: clock times inside a list are not read on local clocks; "
                "give each bound its own lookup, such as __gte and __lte."
            )
    if not any(_is_clock_time(value) for value in lookups.values()):
        return queryset.filter(**lookups)
    return queryset.filter(
        on_local_clocks(
            zone_path,
            zones,
            lambda zone: Q(**{lookup: _bound(lookup, value, zone) for lookup, value in lookups.items()}),
        )
    )


def on_local_clocks(zone_path: str, zones: Iterable, condition: Callable[[tzinfo], Q]) -> Q:
    """Each row held to *condition* as it reads on the clocks of the row's own zone.

    *condition* is called once for each of *zones*, with that zone's clocks, and
    the rows at that zone are held to what it returns — "ends today or later"
    compares each row with the date on its own clocks:
    ``lambda zone: Q(end_date__gte=timezone.localdate(timezone=zone))``.
    *zone_path* and *zones* are as for :func:`filter_on_local_clocks`: a row in
    a zone left out is left out. Compare with values computed for the zone, never
    with parts of a datetime (``__date``, ``__hour``, …), which Django reads in
    one zone for every row.
    """
    combined = Q(pk__in=[])
    for zone in zones:
        clocks = zone if isinstance(zone, tzinfo) else ZoneInfo(str(zone))
        combined |= Q(**{zone_path: zone}) & condition(clocks)
    return combined


# Django computes these parts of a datetime in its one current zone.
_ZONED_PARTS = {
    "date",
    "time",
    "year",
    "iso_year",
    "quarter",
    "month",
    "week",
    "week_day",
    "iso_week_day",
    "day",
    "hour",
    "minute",
    "second",
}


def _refuse_one_zone_readings(model, lookup: str, value) -> None:
    """``TypeError`` for what Django reads in one zone for every row.

    That is a part of a datetime field (``__date``, ``__hour``, …), or a plain
    date given for one, which Django reads as that midnight.
    """
    parts = lookup.split("__")
    for position, part in enumerate(parts):
        try:
            field = model._meta.get_field(part)
        except FieldDoesNotExist:
            return
        if field.is_relation:
            model = field.related_model
            continue
        if not isinstance(field, DateTimeField):
            return
        following = parts[position + 1] if position + 1 < len(parts) else None
        if following in _ZONED_PARTS:
            raise TypeError(
                f"{lookup}: Django reads __{following} in one zone for every row; "
                "compare the datetime itself with bare datetimes, such as __gte and __lt."
            )
        values = value if isinstance(value, (list, tuple, set)) else [value]
        if any(isinstance(item, date) and not isinstance(item, datetime) for item in values):
            raise TypeError(
                f"{lookup}: Django reads a date given for a datetime as midnight in one zone; "
                "give a bare datetime, such as datetime(2026, 11, 1)."
            )
        return


def _is_clock_time(value) -> bool:
    return isinstance(value, datetime) and timezone.is_naive(value)


def _bound(lookup: str, value, zone: tzinfo):
    """The instant a bound in *lookup* stands for on *zone*'s clocks."""
    if not _is_clock_time(value):
        return value
    first = value.replace(tzinfo=zone, fold=0)
    second = value.replace(tzinfo=zone, fold=1)
    if first.utcoffset() == second.utcoffset():
        return first
    if first.astimezone(UTC).astimezone(zone).replace(tzinfo=None) != value:
        return _when_clocks_resume(second, first, zone)
    return second if lookup.endswith(("__lt", "__lte")) else first


def _when_clocks_resume(before: datetime, after: datetime, zone: tzinfo) -> datetime:
    """The instant the clocks jump, between one before the skipped time and one after."""
    low, high = before.astimezone(UTC), after.astimezone(UTC)
    resumed = high.astimezone(zone).utcoffset()
    while high - low > timedelta(microseconds=1):
        middle = low + (high - low) / 2
        if middle.astimezone(zone).utcoffset() == resumed:
            high = middle
        else:
            low = middle
    return high


def _offset(delta: timedelta | None) -> str:
    """``+02:00`` for a UTC offset."""
    minutes = int((delta or timedelta()).total_seconds()) // 60
    sign = "+" if minutes >= 0 else "-"
    return f"{sign}{abs(minutes) // 60:02d}:{abs(minutes) % 60:02d}"
