from django.db import models


class SubscriptionStatus(models.TextChoices):
    """
    Defines the status of a subscription instance.

    ACTIVE: Subscription can be used for making reservations (default)
    FROZEN: Temporarily paused by user (medical leave, vacation, etc.)
    SUSPENDED: Administratively disabled (policy violations, payment issues)
    ARCHIVED: Soft-deleted for business logic exclusion (mistakes, etc.)
    CANCELLED: User-initiated cancellation
    """

    ACTIVE = "ACTIVE", "Active"
    FROZEN = "FROZEN", "Frozen"
    SUSPENDED = "SUSPENDED", "Suspended"
    ARCHIVED = "ARCHIVED", "Archived"
    CANCELLED = "CANCELLED", "Cancelled"
