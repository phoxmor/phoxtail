from django.contrib.auth import get_user_model
from django.db import models
from modelcluster.models import ClusterableModel
from wagtail.admin.panels import FieldPanel, ObjectList, TabbedInterface
from wagtail.search import index

from phoxtail.booking.events.models import Event
from phoxtail.booking.subscriptions.models import Subscription
from phoxtail.core.mixins import AdminURLMixin, TimestampMixin, UUIDMixin

from .constants import ReservationStatus
from .managers import ReservationQuerySet
from .services import ReservationService

User = get_user_model()


class Reservation(UUIDMixin, TimestampMixin, AdminURLMixin, index.Indexed, ClusterableModel):
    """
    Represents a user's reservation for a specific Event. This links a user
    to an event and tracks which subscription was used.
    """

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="reservations",
        help_text="The user who made the reservation.",
    )
    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name="reservations",
        help_text="The specific event being reserved.",
    )
    subscription = models.ForeignKey(
        Subscription,
        on_delete=models.CASCADE,
        related_name="reservations",
        help_text="The user subscription used for this reservation.",
    )
    status = models.CharField(
        max_length=20,
        choices=ReservationStatus.choices,
        default=ReservationStatus.CONFIRMED,
        help_text="Current status of the reservation (e.g., Confirmed, Cancelled, Waitlisted).",
    )
    notes = models.TextField(blank=True, help_text="Any private notes for this reservation.")

    objects = ReservationQuerySet.as_manager()

    details_panels = [
        FieldPanel("user"),
        FieldPanel("event"),
        FieldPanel("subscription"),
        FieldPanel("status"),
        FieldPanel("notes"),
    ]

    edit_handler = TabbedInterface(
        [
            ObjectList(details_panels, heading="Details"),
        ]
    )

    search_fields = [
        index.AutocompleteField("id"),
        index.AutocompleteField("user_username"),
        index.AutocompleteField("user_email", boost=10),
        index.AutocompleteField("user_full_name"),
        index.AutocompleteField("event_service_name"),
        index.AutocompleteField("event_title"),
        index.SearchField("notes"),
        index.FilterField("status"),
        index.FilterField("event"),
        index.FilterField("subscription"),
        index.FilterField("user"),
    ]

    class Meta:
        verbose_name = "Reservation"
        verbose_name_plural = "Reservations"
        unique_together = [["user", "event"]]

    def __str__(self):
        return self.event.service.name

    @property
    def service(self):
        return ReservationService(self)

    @property
    def user_username(self):
        return self.service.get_user_username()

    @property
    def user_first_name(self):
        return self.service.get_user_first_name()

    @property
    def user_last_name(self):
        return self.service.get_user_last_name()

    @property
    def user_email(self):
        return self.service.get_user_email()

    @property
    def user_full_name(self):
        return self.service.get_user_full_name()

    @property
    def event_service_name(self):
        return self.service.get_event_service_name()

    @property
    def event_title(self):
        return self.service.get_event_title()

    @property
    def is_within_allowed_cancellation_period(self):
        return self.service.get_is_within_allowed_cancellation_period()

    @property
    def is_cancelled(self) -> bool:
        """Check if the reservation is cancelled based on status."""
        return self.service.is_cancelled()

    def save(self, *args, **kwargs):
        """
        Custom save method to handle any additional logic before saving.
        """
        super().save(*args, **kwargs)
