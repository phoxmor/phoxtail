from datetime import date
from typing import Optional

from dateutil.relativedelta import relativedelta
from django.utils import timezone


def get_age_time_delta(birth_date: Optional[date]) -> Optional[relativedelta]:
    if birth_date:
        today = timezone.now().date()
        return relativedelta(today, birth_date)
    return None


def get_age_display(birth_date: Optional[date]) -> Optional[str]:
    age = get_age_time_delta(birth_date)
    if age is None:
        return None

    if age.years:
        return f"{age.years} year{'s' if age.years != 1 else ''}"

    if age.months:
        return f"{age.months} month{'s' if age.months != 1 else ''}"

    return f"{age.days} day{'s' if age.days != 1 else ''}"
