from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone
from modelcluster.fields import ParentalKey
from modelcluster.models import ClusterableModel
from wagtail.admin.panels import FieldPanel, InlinePanel, ObjectList, TabbedInterface
from wagtail.models import Orderable
from wagtail.search import index

from phoxtail.booking.core.models import Location
from phoxtail.booking.services.models import Service
from phoxtail.core.mixins import AdminURLMixin, TimestampMixin, UUIDMixin

from .constants import SubscriptionStatus
from .managers import SubscriptionManager, SubscriptionTypeManager
from .services import (
    SubscriptionService,
    SubscriptionTypeService,
)

User = get_user_model()


class SubscriptionType(
    UUIDMixin,
    TimestampMixin,
    AdminURLMixin,
    index.Indexed,
    ClusterableModel,
    Orderable,
):
    """
    Defines the different types of subscriptions available (e.g., "Monthly Unlimited",
    "10-Class Pack").
    """

    location = models.ForeignKey(
        Location,
        on_delete=models.PROTECT,
        related_name="subscription_types",
        null=True,
        help_text="The location where this subscription type is offered.",
    )
    name = models.CharField(
        max_length=255,
        help_text="Name of the subscription type (e.g., 'Monthly Unlimited', '5 Class Pack').",
    )
    description = models.TextField(
        blank=True, help_text="A detailed description of the subscription benefits."
    )
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        help_text="The price of this subscription type.",
    )
    duration = models.PositiveIntegerField(
        blank=True,
        null=True,
        help_text=(
            "Number of days the subscription is valid from purchase date (e.g., 30 for monthly). "
            "Leave blank for an unlimited time period (non-expiring subscription)."
        ),
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Indicates if this subscription type is currently available for purchase.",
    )
    is_public = models.BooleanField(
        default=True,
        help_text="Indicates if this subscription type is currently public.",
    )
    credits = models.PositiveIntegerField(
        blank=True,
        null=True,
        default=0,
        validators=[MinValueValidator(0)],
        help_text="Total shared credits for this subscription type.",
    )
    unpaid_reservation_limit = models.PositiveIntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        help_text="Number of reservations users can make before paying subscriptions of this specific subscription type.",
    )

    objects = SubscriptionTypeManager()

    details_panels = [
        FieldPanel("name"),
        FieldPanel("description"),
    ]

    configuration_panels = [
        FieldPanel("price"),
        FieldPanel("duration"),
        FieldPanel("unpaid_reservation_limit"),
        FieldPanel("location"),
        FieldPanel("is_active"),
        FieldPanel("is_public"),
    ]

    credit_panels = [
        FieldPanel(
            "credits",
            help_text=(
                "Total shared credits for this subscription type. "
                "If credit allocations are defined, the shared pool is available across those exact services. "
                "If no credit allocations are defined, the shared pool is available across all available services. "
                "Leave blank for unlimited shared credits."
            ),
        ),
        InlinePanel(
            "credit_allocations",
            help_text=(
                "Define credits per service. Each allocation specifies how many credits a user gets for that specific service. "
                "Leave credits blank for unlimited access to that service."
            ),
        ),
    ]

    edit_handler = TabbedInterface(
        [
            ObjectList(details_panels, heading="Details"),
            ObjectList(configuration_panels, heading="Configuration"),
            ObjectList(credit_panels, heading="Credits"),
        ],
    )

    search_fields = [
        index.AutocompleteField("name"),
        index.SearchField("description"),
        index.FilterField("is_active"),
    ]

    class Meta:
        verbose_name = "Subscription Type"
        verbose_name_plural = "Subscription Types"
        ordering = ["location__name", "name"]
        unique_together = [["location", "name"]]

    def __str__(self):
        return self.name

    @property
    def service(self) -> "SubscriptionTypeService":
        return SubscriptionTypeService(self)


class SubscriptionTypeCreditAllocation(
    UUIDMixin,
    TimestampMixin,
    AdminURLMixin,
    index.Indexed,
    Orderable,
):
    """
    Defines how many credits are allocated for each service in a subscription type.
    If credits is null/blank, it means unlimited access for that service.
    """

    subscription_type = ParentalKey(
        SubscriptionType,
        on_delete=models.CASCADE,
        related_name="credit_allocations",
    )
    service = models.ForeignKey(
        Service,
        on_delete=models.CASCADE,
        related_name="credit_allocations",
        help_text="The service these credits apply to.",
    )
    credits = models.PositiveIntegerField(
        blank=True,
        null=True,
        default=0,
        help_text="Number of credits allocated for this service. Leave blank for unlimited credits.",
    )

    panels = [
        FieldPanel("subscription_type"),
        FieldPanel("service"),
        FieldPanel("credits"),
    ]

    class Meta:
        unique_together = ["subscription_type", "service"]
        verbose_name = "Credit Allocation"
        verbose_name_plural = "Credit Allocations"

    def __str__(self):
        if self.credits is None:
            return f"{self.service.name}: unlimited credits"
        return f"{self.service.name}: {self.credits} credits"


class Subscription(
    UUIDMixin, TimestampMixin, AdminURLMixin, index.Indexed, ClusterableModel
):
    """
    An instance of a SubscriptionType purchased by a specific user. This tracks
    the user's individual subscription details and remaining credits/duration.
    """

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="subscriptions",
        help_text="The user who owns this subscription.",
    )
    subscription_type = models.ForeignKey(
        SubscriptionType,
        on_delete=models.PROTECT,
        related_name="subscriptions",
        help_text="The type of subscription purchased.",
    )
    start_date = models.DateField(
        default=timezone.now, help_text="The date this subscription became active."
    )
    end_date = models.DateField(
        blank=True,
        null=True,
        help_text="The date this subscription expires. Calculated based on SubscriptionType duration.",
    )
    status = models.CharField(
        max_length=20,
        choices=SubscriptionStatus.choices,
        default=SubscriptionStatus.ACTIVE,
        help_text="Current status of the subscription (active, frozen, suspended, etc.)",
    )

    credits = models.PositiveIntegerField(
        blank=True,
        null=True,
        default=0,
        validators=[MinValueValidator(0)],
        help_text="Remaining credits from shared pool for this user's subscription.",
    )
    is_paid = models.BooleanField(
        default=False,
        help_text="Indicates if this subscription has been fully paid for.",
    )
    unpaid_reservation_limit = models.PositiveIntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        help_text="Number of reservations this user can make before paying this subscription.",
    )

    objects = SubscriptionManager()

    details_panels = [
        FieldPanel("user"),
        FieldPanel("subscription_type"),
        FieldPanel("start_date"),
        FieldPanel("end_date"),
        FieldPanel("status"),
        FieldPanel("is_paid"),
        FieldPanel("unpaid_reservation_limit"),
    ]

    credit_panels = [
        FieldPanel(
            "credits",
            help_text=(
                "Remaining credits from the shared pool. This is the user's current balance of credits that can be used across multiple services. "
                "Leave blank for unlimited shared credits. Set to 0 if this subscription only uses per-service credit balances."
            ),
        ),
        InlinePanel(
            "credit_balances",
            label="Credit Balances",
            help_text=(
                "Track remaining credits per individual service for this user's subscription. "
                "Each balance shows how many credits the user has left for that specific service. "
                "Leave credits blank for unlimited access to that service."
            ),
        ),
    ]

    edit_handler = TabbedInterface(
        [
            ObjectList(details_panels, heading="Details"),
            ObjectList(credit_panels, heading="Credits"),
        ]
    )

    search_fields = [
        index.AutocompleteField("id"),
        index.AutocompleteField("user_first_name"),
        index.AutocompleteField("user_last_name"),
        index.AutocompleteField("user_username"),
        index.AutocompleteField("user_email", boost=10),
        index.AutocompleteField("subscription_type_name"),
        index.FilterField("subscription_type"),
        index.FilterField("status"),
        index.FilterField("start_date"),
        index.FilterField("end_date"),
        index.FilterField("user"),
    ]

    class Meta:
        verbose_name = "Subscription"
        verbose_name_plural = "Subscriptions"
        ordering = ["-start_date"]

    def __str__(self):
        return f"{self.user.get_full_name()} - {self.subscription_type.name}"

    @property
    def user_first_name(self):
        return self.service.get_user_first_name()

    @property
    def user_last_name(self):
        return self.service.get_user_last_name()

    @property
    def user_username(self):
        return self.service.get_user_username()

    @property
    def user_email(self):
        return self.service.get_user_email()

    @property
    def subscription_type_name(self):
        return self.service.get_subscription_type_name()

    @property
    def service(self) -> "SubscriptionService":
        return SubscriptionService(self)

    # All these methods now delegate to the service
    def get_credits_for_service(self, service: "Service"):
        return self.service.get_credits_for_service(service)

    def use_credit(self, service: "Service"):
        return self.service.use_credit(service)

    def can_access_service(self, service: "Service"):
        return self.service.can_access_service(service)

    def has_remaining_credits(self) -> bool:
        return self.service.has_remaining_credits()

    def has_remaining_shared_credits(self) -> bool:
        return self.service.has_remaining_shared_credits()

    def has_remaining_per_service_credits(self, service: "Service" = None) -> bool:
        return self.service.has_remaining_per_service_credits(service)

    @property
    def is_expired(self) -> bool:
        """
        Check if the subscription is expired.
        Delegates to the service layer for business logic.
        """
        return self.service.is_expired()

    @property
    def remaining_grace_period_reservations(self) -> int:
        """Get the number of grace period reservations remaining before payment is required."""
        return self.service.get_remaining_grace_period_reservations()

    @property
    def can_renew(self) -> bool:
        """Check if the subscription can be renewed."""
        return self.service.can_renew()

    @property
    def renewal_end_date(self):
        """Get the end date for a renewed subscription."""
        return self.service.get_renewal_end_date()


class SubscriptionCreditBalance(
    UUIDMixin, TimestampMixin, AdminURLMixin, index.Indexed, Orderable
):
    """
    Tracks the remaining credits for each service within a user's subscription.
    Only exists for services with limited credits (not unlimited).
    """

    subscription = ParentalKey(
        Subscription,
        on_delete=models.CASCADE,
        related_name="credit_balances",
    )
    service = models.ForeignKey(
        Service,
        on_delete=models.CASCADE,
        help_text="The service these credits apply to.",
    )
    credits = models.PositiveIntegerField(
        blank=True,
        null=True,
        default=0,
        help_text="Number of credits remaining for this service. Leave blank for unlimited access.",
    )

    panels = [
        FieldPanel("service"),
        FieldPanel("credits"),
    ]

    class Meta:
        unique_together = ["subscription", "service"]
        verbose_name = "Credit Balance"
        verbose_name_plural = "Credit Balances"

    def __str__(self):
        return f"{self.subscription.user.username} - {self.service.name}: {self.credits} credits"
