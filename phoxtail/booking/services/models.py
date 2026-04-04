from django.db import models
from wagtail.admin.panels import FieldPanel, ObjectList, TabbedInterface
from wagtail.search import index

from phoxtail.core.mixins import AdminURLMixin, TimestampMixin, UUIDMixin


class Service(UUIDMixin, TimestampMixin, AdminURLMixin, index.Indexed, models.Model):
    """
    Represents a specific service offering (e.g., "Pilates Mat Class",
    "Reformer Session"). This defines the general characteristics of a service product.
    """

    name = models.CharField(
        max_length=255,
        unique=True,
        help_text="Name of the specific service offering (e.g., 'Pilates Mat Class', 'Reformer Session').",
    )
    description = models.TextField(
        blank=True, help_text="A brief description of what this service entails."
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Indicates if this service offering is currently available.",
    )
    cancellation_lockout_hours = models.PositiveIntegerField(
        default=1,
        help_text="Number of hours before the event start time after which cancellations are not allowed.",
    )
    palette = models.ForeignKey(
        "phoxtail_design.Palette",
        on_delete=models.SET_NULL,
        related_name="services",
        null=True,
        blank=True,
        help_text="Select a color palette for the service",
    )

    details_panels = [
        FieldPanel("name"),
        FieldPanel("description"),
        FieldPanel("is_active"),
        FieldPanel("cancellation_lockout_hours"),
        FieldPanel("palette"),
    ]

    configuration_panels = []

    edit_handler = TabbedInterface(
        [
            ObjectList(details_panels, heading="Details"),
            ObjectList(configuration_panels, heading="Configuration"),
        ]
    )

    search_fields = [
        index.AutocompleteField("name", partial_match=True, boost=10),
        index.SearchField("description"),
        index.FilterField("is_active"),
    ]

    class Meta:
        verbose_name = "Service"
        verbose_name_plural = "Services"
        ordering = ["name"]

    def __str__(self):
        return self.name
