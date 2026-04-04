from django.utils import timezone

from .models import Reservation


def get_reservation_list_context(user):
    """
    Helper function to get reservations context for a user.
    """
    reservations = (
        Reservation.objects.filter(user=user, event__start_datetime__gte=timezone.now())
        .select_related(
            "event", "event__service", "event__space", "event__space__location"
        )
        .order_by("event__start_datetime")
    )
    return {"reservations": reservations}
