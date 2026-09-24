"""A datetime given for a place is read on that place's clocks, or refused.

Berlin is at +02:00 until 25 Oct 2026 and at +01:00 after. On 29 Mar its
clocks skip 02:00–03:00; on 25 Oct they show 02:00–03:00 twice.
"""

from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest
from django.core.exceptions import ValidationError

from phoxtail.core.clocks import localize

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
