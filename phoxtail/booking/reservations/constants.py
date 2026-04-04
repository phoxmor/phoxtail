from django.db import models


class ReservationStatus(models.TextChoices):
    COMPLETED = "COMPLETED", "Completed"
    CONFIRMED = "CONFIRMED", "Confirmed"
    CANCELLED = "CANCELLED", "Cancelled"
    WAITLISTED = "WAITLISTED", "Waitlisted"
    NO_SHOW = "NO_SHOW", "No Show"
