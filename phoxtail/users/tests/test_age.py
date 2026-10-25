"""A person's age reads in its largest whole unit, counted by calendar."""

from __future__ import annotations

from datetime import date

import pytest
from freezegun import freeze_time

from phoxtail.users.utils import get_age_display, get_age_time_delta


@freeze_time("2026-03-01")
@pytest.mark.parametrize(
    ("born_at", "expected"),
    [
        (date(2005, 3, 1), "21 years"),
        (date(2025, 3, 1), "1 year"),
        # A day short of a year still reads in months.
        (date(2025, 3, 2), "11 months"),
        (date(2026, 1, 31), "1 month"),
        # February is short: a calendar month, not 30 days.
        (date(2026, 2, 1), "1 month"),
        (date(2026, 2, 28), "1 day"),
        (date(2026, 3, 1), "0 days"),
    ],
)
def test_age_display(born_at, expected):
    assert get_age_display(born_at) == expected


@freeze_time("2026-03-01")
def test_age_time_delta_counts_calendar_parts():
    age = get_age_time_delta(date(2000, 1, 15))
    assert (age.years, age.months, age.days) == (26, 1, 14)


def test_no_birth_date_has_no_age():
    assert get_age_time_delta(None) is None
    assert get_age_display(None) is None
