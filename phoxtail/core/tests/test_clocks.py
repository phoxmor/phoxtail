"""A datetime given for a place is read on that place's clocks, or refused.

Berlin is at +02:00 until 25 Oct 2026 and at +01:00 after. On 29 Mar its
clocks skip 02:00–03:00; on 25 Oct they show 02:00–03:00 twice.
"""

from __future__ import annotations

import re
from datetime import UTC, date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest
from django.core.exceptions import ValidationError

from phoxtail.core.clocks import _bound, filter_on_local_clocks, localize
from phoxtail.core.tests.testapp.models import Occurrence

BERLIN = ZoneInfo("Europe/Berlin")


def test_a_bare_time_is_read_on_the_zones_clocks():
    value = localize(datetime(2026, 11, 2, 9, 0), BERLIN)

    assert value == datetime(2026, 11, 2, 8, 0, tzinfo=UTC)
    assert value.utcoffset().total_seconds() == 3600


def test_a_time_with_the_zones_offset_is_kept():
    given = datetime.fromisoformat("2026-11-02T09:00+01:00")

    assert localize(given, BERLIN) == given


def test_utc_is_kept_where_the_zone_is_at_utc():
    given = datetime(2026, 11, 2, 9, 0, tzinfo=UTC)

    assert localize(given, ZoneInfo("UTC")) == given


@pytest.mark.parametrize(
    "given",
    [
        pytest.param("2026-11-02T09:00+02:00", id="last-seasons-offset"),
        pytest.param("2026-11-02T08:00Z", id="utc"),
    ],
)
def test_a_time_with_another_offset_is_refused_naming_the_zones(given):
    with pytest.raises(ValidationError, match=r"\+01:00") as refused:
        localize(datetime.fromisoformat(given), BERLIN)

    assert refused.value.code == "offset_mismatch"


def test_a_bare_time_the_clocks_skip_is_refused():
    with pytest.raises(ValidationError, match="does not exist") as refused:
        localize(datetime(2026, 3, 29, 2, 30), BERLIN)

    assert refused.value.code == "nonexistent_time"


def test_a_bare_time_the_clocks_repeat_is_refused_naming_both_offsets():
    with pytest.raises(ValidationError, match=r"\+02:00.*\+01:00") as refused:
        localize(datetime(2026, 10, 25, 2, 30), BERLIN)

    assert refused.value.code == "ambiguous_time"


@pytest.mark.parametrize(
    ("given", "utc_hour"),
    [
        pytest.param("2026-10-25T02:30+02:00", 0, id="first"),
        pytest.param("2026-10-25T02:30+01:00", 1, id="second"),
    ],
)
def test_the_offset_picks_which_repeated_time_is_meant(given, utc_hour):
    value = localize(datetime.fromisoformat(given), BERLIN)

    assert value == datetime(2026, 10, 25, utc_hour, 30, tzinfo=UTC)


def test_a_time_already_in_the_zone_that_its_clocks_skip_is_refused():
    with pytest.raises(ValidationError) as refused:
        localize(datetime(2026, 3, 29, 2, 30, tzinfo=BERLIN), BERLIN)

    assert refused.value.code == "offset_mismatch"


# --- filter_on_local_clocks: a bare bound is read on each row's own clocks.

CAIRO = "Africa/Cairo"  # its clocks skip 00:00–01:00 on 24 Apr 2026: that day has no midnight
ZONES = ("Europe/Athens", "Europe/Berlin", CAIRO)  # more than any one test's rows are at: that costs nothing


def _starting(*moments):
    return [Occurrence.objects.create(start_datetime=moment, zone=zone) for zone, moment in moments]


def _kept(**lookups):
    kept = filter_on_local_clocks(Occurrence.objects.all(), "zone", ZONES, **lookups)
    return set(kept.values_list("zone", flat=True))


@pytest.mark.django_db
def test_a_bare_day_is_each_rows_own():
    same_moment = datetime(2026, 10, 31, 22, 30, tzinfo=UTC)  # 00:30 Sun in Athens, 23:30 Sat in Berlin
    _starting(("Europe/Athens", same_moment), ("Europe/Berlin", same_moment))

    sunday = _kept(start_datetime__gte=datetime(2026, 11, 1), start_datetime__lt=datetime(2026, 11, 2))

    assert sunday == {"Europe/Athens"}


@pytest.mark.django_db
def test_a_bound_with_an_offset_is_one_moment_for_every_row():
    same_moment = datetime(2026, 10, 31, 22, 30, tzinfo=UTC)
    _starting(("Europe/Athens", same_moment), ("Europe/Berlin", same_moment))

    assert _kept(start_datetime__gte=same_moment) == {"Europe/Athens", "Europe/Berlin"}


@pytest.mark.django_db
def test_a_day_whose_midnight_the_clocks_skip_starts_when_they_resume():
    _starting(
        (CAIRO, datetime(2026, 4, 23, 21, 30, tzinfo=UTC)),  # 23:30 on the 23rd
        (CAIRO, datetime(2026, 4, 23, 22, 15, tzinfo=UTC)),  # 01:15 on the 24th
    )

    kept = filter_on_local_clocks(
        Occurrence.objects.order_by("start_datetime"),
        "zone",
        ZONES,
        start_datetime__gte=datetime(2026, 4, 24),
        start_datetime__lt=datetime(2026, 4, 25),
    )

    assert [row.start_datetime for row in kept] == [datetime(2026, 4, 23, 22, 15, tzinfo=UTC)]


@pytest.mark.django_db
def test_a_bound_inside_the_skipped_hour_starts_when_the_clocks_resume():
    _starting(("Europe/Berlin", datetime(2026, 3, 29, 1, 10, tzinfo=UTC)))  # 03:10, just after the jump

    assert _kept(start_datetime__gte=datetime(2026, 3, 29, 2, 30)) == {"Europe/Berlin"}


@pytest.mark.django_db
def test_an_upper_bound_on_a_repeated_time_is_its_second_showing():
    _starting(("Europe/Berlin", datetime(2026, 10, 25, 1, 15, tzinfo=UTC)))  # 02:15, the second time round

    assert _kept(start_datetime__lte=datetime(2026, 10, 25, 2, 30)) == {"Europe/Berlin"}


@pytest.mark.django_db
def test_a_row_in_a_zone_left_out_is_left_out():
    same_moment = datetime(2026, 10, 31, 22, 30, tzinfo=UTC)
    _starting(("Europe/Athens", same_moment), ("Europe/Berlin", same_moment))

    kept = filter_on_local_clocks(
        Occurrence.objects.all(), "zone", ["Europe/Athens"], start_datetime__lt=datetime(2027, 1, 1)
    )

    assert set(kept.values_list("zone", flat=True)) == {"Europe/Athens"}


@pytest.mark.parametrize(
    "lookups",
    [
        pytest.param({"start_datetime__range": (datetime(2026, 11, 1), datetime(2026, 11, 2))}, id="range"),
        pytest.param({"start_datetime__in": [datetime(2026, 11, 1)]}, id="in"),
    ],
)
def test_clock_times_inside_a_list_are_refused_rather_than_read_as_utc(lookups):
    with pytest.raises(TypeError, match="__gte"):
        filter_on_local_clocks(Occurrence.objects.all(), "zone", ZONES, **lookups)


@pytest.mark.parametrize(
    "lookups",
    [
        pytest.param({"start_datetime__date": date(2026, 11, 1)}, id="date"),
        pytest.param({"start_datetime__hour__gte": 18}, id="hour"),
        pytest.param({"start_datetime__time__gte": time(18)}, id="time"),
        pytest.param({"start_datetime__week_day": 1}, id="week_day"),
    ],
)
def test_parts_of_a_datetime_are_refused_rather_than_read_in_one_zone(lookups):
    with pytest.raises(TypeError, match="__gte"):
        filter_on_local_clocks(Occurrence.objects.all(), "zone", ZONES, **lookups)


@pytest.mark.parametrize(
    "lookups",
    [
        pytest.param({"start_datetime__gte": date(2026, 11, 1)}, id="date"),
        pytest.param({"start_datetime__in": [date(2026, 11, 1)]}, id="dates-in-a-list"),
    ],
)
def test_a_date_for_a_datetime_is_refused_rather_than_read_as_midnight_utc(lookups):
    with pytest.raises(TypeError, match="datetime"):
        filter_on_local_clocks(Occurrence.objects.all(), "zone", ZONES, **lookups)


# --- Every clock change of 2026 in zones that change in unusual ways.

AWKWARD_ZONES = (
    "Australia/Lord_Howe",  # changes by 30 minutes
    "Europe/Dublin",  # the database records its daylight saving as negative, in winter
    "America/Santiago",  # changes at midnight
    "Pacific/Chatham",  # +12:45 and +13:45
    "America/St_Johns",  # -03:30 and -02:30
    "Africa/Casablanca",  # steps back for Ramadan
)


def _changes(name):
    """``(instant, offset before, offset after)`` for each clock change of 2026 in *name*."""
    zone = ZoneInfo(name)
    found, moment = [], datetime(2026, 1, 1, tzinfo=UTC)
    while moment.year == 2026:
        after = moment + timedelta(hours=1)
        if moment.astimezone(zone).utcoffset() != after.astimezone(zone).utcoffset():
            low, high = moment, after
            while high - low > timedelta(minutes=1):
                middle = low + (high - low) / 2
                if middle.astimezone(zone).utcoffset() == after.astimezone(zone).utcoffset():
                    high = middle
                else:
                    low = middle
            found.append((high, low.astimezone(zone).utcoffset(), high.astimezone(zone).utcoffset()))
        moment = after
    return found


def _bound_instant(value, zone, upper=False):
    """The instant the filter reads a bound as, for a lower bound or an upper one."""
    return _bound("start_datetime__lte" if upper else "start_datetime__gte", value, zone).astimezone(UTC)


def _written(offset):
    return datetime(2026, 1, 1, tzinfo=timezone(offset)).isoformat()[-6:]


CHANGES = [
    pytest.param(name, *change, id=f"{name}-{change[0]:%m-%d}") for name in AWKWARD_ZONES for change in _changes(name)
]


@pytest.mark.parametrize(("name", "instant", "before", "after"), CHANGES)
def test_every_clock_change_is_read_exactly(name, instant, before, after):
    zone = ZoneInfo(name)
    naive = instant.replace(tzinfo=None)
    minute = timedelta(minutes=1)
    if after > before:  # the clocks jump: [instant + before, instant + after) never shows
        first_skipped, resumed = naive + before, naive + after
        skipped = first_skipped + (after - before) / 2
        with pytest.raises(ValidationError) as refused:
            localize(skipped, zone)
        assert refused.value.code == "nonexistent_time"
        assert localize(first_skipped - minute, zone) == instant - minute
        assert localize(resumed, zone) == instant
        assert _bound_instant(skipped, zone) == instant
    else:  # the clocks go back: [instant + after, instant + before) shows twice
        repeated = naive + after + (before - after) / 2
        with pytest.raises(ValidationError, match=rf"{re.escape(_written(before))} or {re.escape(_written(after))}"):
            localize(repeated, zone)
        assert _bound_instant(repeated, zone) == (repeated - before).replace(tzinfo=UTC)
        assert _bound_instant(repeated, zone, upper=True) == (repeated - after).replace(tzinfo=UTC)
        assert localize(naive + after - minute, zone) == instant - (before - after) - minute
        assert localize(naive + before, zone) == instant + (before - after)


def test_every_awkward_zone_changes_its_clocks_in_2026():
    assert all(_changes(name) for name in AWKWARD_ZONES)
