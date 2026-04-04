from django.contrib.auth import get_user_model
from django.core.validators import URLValidator
from django.db import models
from django.utils.text import slugify
from django_countries.fields import CountryField
from modelcluster.fields import ParentalKey
from modelcluster.models import ClusterableModel
from phonenumber_field.modelfields import PhoneNumberField
from timezone_field import TimeZoneField
from wagtail.admin.panels import FieldPanel, InlinePanel, ObjectList, TabbedInterface
from wagtail.models import Orderable
from wagtail.search import index

from phoxtail.core.mixins import AdminURLMixin, TimestampMixin, UUIDMixin

from .services import StaffService

User = get_user_model()

# Import so Django's model autodetector finds it in this app's models module.
from .permissions.models import BookingAdminPermission  # noqa: E402, F401


class BookingGroup(
    UUIDMixin, TimestampMixin, AdminURLMixin, index.Indexed, models.Model
):
    """
    A named group of users for controlling access to booking resources (events,
    services, etc.). Completely separate from Django's auth Group model to avoid
    mixing with system groups like Moderators/Editors.

    Designed to grow into a full membership/cohort system with invite links,
    subscription-based auto-assignment, and per-user expiry.
    """

    name = models.CharField(
        max_length=255,
        unique=True,
        help_text="Name of the group (e.g., 'Premium Members', 'Private Retreat').",
    )
    slug = models.SlugField(
        max_length=255,
        unique=True,
        blank=True,
        help_text="URL-friendly identifier. Auto-generated from name if left blank.",
    )
    description = models.TextField(
        blank=True,
        help_text="Optional description of this group's purpose or membership criteria.",
    )
    members = models.ManyToManyField(
        User,
        blank=True,
        related_name="booking_groups",
        help_text="Users who are members of this group.",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Inactive groups block access as if the user were not a member.",
    )

    panels = [
        FieldPanel("name"),
        FieldPanel("slug"),
        FieldPanel("description"),
        FieldPanel("members"),
        FieldPanel("is_active"),
    ]

    search_fields = [
        index.AutocompleteField("name", boost=10),
        index.SearchField("description"),
        index.FilterField("is_active"),
    ]

    class Meta:
        verbose_name = "Booking Group"
        verbose_name_plural = "Booking Groups"
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug and self.name:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def has_member(self, user: User) -> bool:
        """Check if a user is an active member of this group."""
        if not self.is_active:
            return False
        return self.members.filter(pk=user.pk).exists()


class Location(
    UUIDMixin, TimestampMixin, AdminURLMixin, index.Indexed, ClusterableModel, Orderable
):
    """
    Represents a physical address or establishment where events can take place.
    Designed for comprehensive global identification and contact information.
    Registered as a Wagtail Snippet for easy management in the CMS.
    """

    name = models.CharField(
        max_length=255,
        unique=True,
        help_text="Official name of the location or establishment (e.g., 'City Convention Center', 'Downtown Office').",
    )
    slug = models.SlugField(
        max_length=255,
        unique=True,
        blank=True,
        help_text="Unique, URL-friendly identifier for the location. Auto-generated from name if left blank.",
    )
    description = models.TextField(
        blank=True,
        help_text="A brief description providing general information about the location.",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Indicates if this location is currently operational and available for events.",
    )

    street_address_line1 = models.CharField(
        max_length=255,
        help_text="Primary street address line (e.g., '123 Main St').",
    )
    street_address_line2 = models.CharField(
        max_length=255,
        blank=True,
        help_text="Secondary address information (e.g., 'Suite 400', 'Unit B').",
    )
    city = models.CharField(
        max_length=100, help_text="The city where the location is situated."
    )
    state_province = models.CharField(
        max_length=100,
        blank=True,
        help_text="The state, province, or region of the location (e.g., 'California', 'Ontario').",
    )
    postal_code = models.CharField(
        max_length=20,
        blank=True,
        help_text="The postal code or zip code of the location.",
    )
    country = CountryField(
        blank_label="(Select Country)",
        help_text="The country where this location is situated.",
    )
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        help_text="Geographical latitude coordinate of the location for mapping (e.g., 51.5074).",
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        help_text="Geographical longitude coordinate of the location for mapping (e.1g., -0.1278).",
    )
    timezone = TimeZoneField(
        default="UTC",
        help_text="The local timezone of the location, essential for accurate event scheduling.",
    )

    phone_number = PhoneNumberField(
        help_text="Primary contact phone number for the location (e.g., +12125550101).",
    )
    email = models.EmailField(
        max_length=255,
        help_text="Primary contact email address for the location.",
    )
    website = models.URLField(
        max_length=255,
        blank=True,
        validators=[URLValidator()],
        help_text="Official website URL for this specific location, if available.",
    )

    details_panels = [
        FieldPanel("name"),
        FieldPanel("slug"),
        FieldPanel("description"),
        FieldPanel("is_active"),
    ]

    address_panels = [
        FieldPanel("street_address_line1"),
        FieldPanel("street_address_line2"),
        FieldPanel("city"),
        FieldPanel("state_province"),
        FieldPanel("postal_code"),
        FieldPanel("country"),
        FieldPanel("latitude"),
        FieldPanel("longitude"),
        FieldPanel("timezone"),
    ]

    contact_panels = [
        FieldPanel("phone_number"),
        FieldPanel("email"),
        FieldPanel("website"),
    ]

    spaces_panels = [
        InlinePanel("spaces", label="Spaces"),
    ]

    edit_handler = TabbedInterface(
        [
            ObjectList(details_panels, heading="Details"),
            ObjectList(address_panels, heading="Address"),
            ObjectList(contact_panels, heading="Contact"),
            ObjectList(spaces_panels, heading="Spaces"),
        ]
    )

    search_fields = [
        index.AutocompleteField("name", boost=10),
        index.SearchField("description"),
        index.FilterField("city"),
        index.FilterField("country"),
        index.FilterField("is_active"),
    ]

    class Meta:
        verbose_name = "Location"
        verbose_name_plural = "Locations"
        ordering = ["country", "city", "name"]
        indexes = [
            models.Index(fields=["latitude", "longitude"]),
            models.Index(fields=["city", "country"]),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug and self.name:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    @property
    def full_address(self):
        parts = [self.street_address_line1]
        if self.street_address_line2:
            parts.append(self.street_address_line2)
        parts.append(self.city)
        if self.state_province:
            parts.append(self.state_province)
        if self.postal_code:
            parts.append(self.postal_code)
        if self.country:
            parts.append(str(self.country))

        return ", ".join(filter(None, parts))

    @property
    def map_link(self):
        if self.latitude is not None and self.longitude is not None:
            return f"https://www.google.com/maps/search/?api=1&query={self.latitude},{self.longitude}"
        return None


class Space(UUIDMixin, TimestampMixin, AdminURLMixin, index.Indexed, Orderable):
    """
    Represents a specific, reservable area within a Location, such as an
    enclosed room, an open hall, or an outdoor zone, where events can be held.
    Registered as a Wagtail Snippet for easy management in the CMS.
    """

    location = ParentalKey(
        Location,
        on_delete=models.CASCADE,
        related_name="spaces",
        help_text="The parent location to which this reservable space belongs.",
    )
    name = models.CharField(
        max_length=100,
        help_text="Descriptive name of the space (e.g., 'Conference Room A', 'Main Hall', 'Outdoor Pitch 3').",
    )
    description = models.TextField(
        blank=True,
        help_text="Detailed description of the space, its features, and suitable uses.",
    )
    capacity = models.PositiveIntegerField(
        default=0,
        help_text="Maximum number of individuals this space can comfortably accommodate for an event.",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Indicates if this space is currently available for scheduling events.",
    )

    panels = [
        FieldPanel("location"),
        FieldPanel("name"),
        FieldPanel("description"),
        FieldPanel("capacity"),
        FieldPanel("is_active"),
    ]

    search_fields = [
        index.AutocompleteField("name"),
        index.SearchField("description"),
        index.FilterField("location"),
        index.FilterField("is_active"),
    ]

    class Meta:
        verbose_name = "Space"
        verbose_name_plural = "Spaces"
        unique_together = [["location", "name"]]
        ordering = ["location__name", "name"]

    def __str__(self):
        return self.name


class Staff(UUIDMixin, TimestampMixin, AdminURLMixin, index.Indexed, models.Model):
    """
    Represents a staff member or instructor. This model links to your custom
    User model to provide detailed staff profiles.
    """

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="staff",
        help_text="The user account associated with this staff member.",
    )
    bio = models.TextField(
        blank=True,
        help_text="A brief biography or description of the staff member's role and expertise.",
    )

    panels = [
        FieldPanel("user"),
        FieldPanel("bio"),
    ]

    search_fields = [
        index.AutocompleteField("user_username"),
        index.AutocompleteField("user_email", boost=10),
        index.AutocompleteField("user_full_name"),
        index.SearchField("bio"),
    ]

    class Meta:
        verbose_name = "Staff"
        verbose_name_plural = "Staff"

    def __str__(self):
        return self.user.get_full_name() if self.user else "Staff Member (No User)"

    @property
    def service(self):
        return StaffService(self)

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
