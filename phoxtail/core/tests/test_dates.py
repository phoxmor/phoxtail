from datetime import date, datetime

from django.utils import translation

from phoxtail.core.dates import display_date


def test_display_date_writes_weekday_day_month_and_year():
    with translation.override("en"):
        assert display_date(date(2026, 10, 5)) == "Mon, Oct 5, 2026"


def test_display_date_reads_a_date_and_time_as_its_date():
    with translation.override("en"):
        assert display_date(datetime(2026, 10, 5, 23, 30)) == "Mon, Oct 5, 2026"


def test_display_date_is_in_the_page_language():
    with translation.override("de"):
        assert display_date(date(2026, 10, 5)) == "Mo., 5. Okt. 2026"
