from django.db import models
from django.db.models import Q
from django.utils import timezone


class EventManager(models.Manager):
    def active_recurrence_templates(self, as_of=None) -> models.QuerySet:
        """
        Retrieves active recurrence templates for generating/projecting future events.

        An **active template** is an event with `is_recurrence_template=True`,
        has `recurrence_freq` set, and a `recurrence_until` date/time that is
        either null (no end) or in the future/present relative to `as_of`.

        Args:
            as_of: Optional datetime to check template activity against.
                   If `None`, uses current time (timezone.now()).

        Returns:
            A `QuerySet` containing active template events ordered by `start_datetime`.
        """
        if as_of is None:
            as_of = timezone.now()

        return self.filter(
            Q(is_recurrence_template=True),
            Q(recurrence_freq__isnull=False),
            Q(recurrence_until__isnull=True) | Q(recurrence_until__gte=as_of),
        ).order_by("start_datetime")
