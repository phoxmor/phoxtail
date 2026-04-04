from django.db import models
from django.db.models import Case, IntegerField, Value, When

from .constants import ReservationStatus


class ReservationQuerySet(models.QuerySet):
    def with_status_order(self):
        """Annotate and order by custom status priority."""
        return self.annotate(
            status_order=Case(
                When(status=ReservationStatus.COMPLETED, then=Value(0)),
                When(status=ReservationStatus.CONFIRMED, then=Value(1)),
                When(status=ReservationStatus.WAITLISTED, then=Value(2)),
                When(status=ReservationStatus.CANCELLED, then=Value(3)),
                When(status=ReservationStatus.NO_SHOW, then=Value(4)),
                default=Value(5),
                output_field=IntegerField(),
            )
        ).order_by("status_order", "created_at")
