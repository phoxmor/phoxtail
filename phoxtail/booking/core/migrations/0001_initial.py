import django.core.validators
import django.db.models.deletion
import django_countries.fields
import modelcluster.fields
import modelsearch.index
import phoxtail.core.mixins
import phonenumber_field.modelfields
import timezone_field.fields
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="BookingAdminPermission",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
            ],
            options={
                "verbose_name": "Booking",
                "verbose_name_plural": "Booking",
                "permissions": [
                    ("access_booking_management", "Can access booking management"),
                    ("manage_reservations", "Can create, edit, move reservations"),
                    (
                        "manage_booking_event_details",
                        "Can edit event details in booking view",
                    ),
                    (
                        "access_scheduling_management",
                        "Can access scheduling management",
                    ),
                    ("create_scheduled_events", "Can create events in scheduling"),
                    ("edit_scheduled_events", "Can edit events in scheduling"),
                    ("delete_scheduled_events", "Can delete events in scheduling"),
                    (
                        "bulk_update_scheduled_events",
                        "Can bulk-update event status",
                    ),
                    ("access_billing_management", "Can access billing management"),
                    (
                        "manage_billing_subscriptions",
                        "Can create and edit subscriptions",
                    ),
                    ("access_users_management", "Can access users management"),
                    ("create_booking_users", "Can create users"),
                    ("edit_booking_users", "Can edit users"),
                    ("access_booking_settings", "Can access booking settings"),
                ],
                "default_permissions": (),
            },
        ),
        migrations.CreateModel(
            name="BookingGroup",
            fields=[
                (
                    "id",
                    models.BigAutoField(primary_key=True, serialize=False),
                ),
                (
                    "uuid",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, unique=True
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True, null=True),
                ),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "name",
                    models.CharField(
                        help_text="Name of the group (e.g., 'Premium Members', 'Private Retreat').",
                        max_length=255,
                        unique=True,
                    ),
                ),
                (
                    "slug",
                    models.SlugField(
                        blank=True,
                        help_text="URL-friendly identifier. Auto-generated from name if left blank.",
                        max_length=255,
                        unique=True,
                    ),
                ),
                (
                    "description",
                    models.TextField(
                        blank=True,
                        help_text="Optional description of this group's purpose or membership criteria.",
                    ),
                ),
                (
                    "is_active",
                    models.BooleanField(
                        default=True,
                        help_text="Inactive groups block access as if the user were not a member.",
                    ),
                ),
                (
                    "members",
                    models.ManyToManyField(
                        blank=True,
                        help_text="Users who are members of this group.",
                        related_name="booking_groups",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Booking Group",
                "verbose_name_plural": "Booking Groups",
                "ordering": ["name"],
            },
            bases=(
                phoxtail.core.mixins.AdminURLMixin,
                modelsearch.index.Indexed,
                models.Model,
            ),
        ),
        migrations.CreateModel(
            name="Location",
            fields=[
                (
                    "sort_order",
                    models.IntegerField(blank=True, editable=False, null=True),
                ),
                (
                    "id",
                    models.BigAutoField(primary_key=True, serialize=False),
                ),
                (
                    "uuid",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, unique=True
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True, null=True),
                ),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "name",
                    models.CharField(
                        help_text="Official name of the location or establishment (e.g., 'City Convention Center', 'Downtown Office').",
                        max_length=255,
                        unique=True,
                    ),
                ),
                (
                    "slug",
                    models.SlugField(
                        blank=True,
                        help_text="Unique, URL-friendly identifier for the location. Auto-generated from name if left blank.",
                        max_length=255,
                        unique=True,
                    ),
                ),
                (
                    "description",
                    models.TextField(
                        blank=True,
                        help_text="A brief description providing general information about the location.",
                    ),
                ),
                (
                    "is_active",
                    models.BooleanField(
                        default=True,
                        help_text="Indicates if this location is currently operational and available for events.",
                    ),
                ),
                (
                    "street_address_line1",
                    models.CharField(
                        help_text="Primary street address line (e.g., '123 Main St').",
                        max_length=255,
                    ),
                ),
                (
                    "street_address_line2",
                    models.CharField(
                        blank=True,
                        help_text="Secondary address information (e.g., 'Suite 400', 'Unit B').",
                        max_length=255,
                    ),
                ),
                (
                    "city",
                    models.CharField(
                        help_text="The city where the location is situated.",
                        max_length=100,
                    ),
                ),
                (
                    "state_province",
                    models.CharField(
                        blank=True,
                        help_text="The state, province, or region of the location (e.g., 'California', 'Ontario').",
                        max_length=100,
                    ),
                ),
                (
                    "postal_code",
                    models.CharField(
                        blank=True,
                        help_text="The postal code or zip code of the location.",
                        max_length=20,
                    ),
                ),
                (
                    "country",
                    django_countries.fields.CountryField(
                        help_text="The country where this location is situated.",
                        max_length=2,
                    ),
                ),
                (
                    "latitude",
                    models.DecimalField(
                        blank=True,
                        decimal_places=6,
                        help_text="Geographical latitude coordinate of the location for mapping (e.g., 51.5074).",
                        max_digits=9,
                        null=True,
                    ),
                ),
                (
                    "longitude",
                    models.DecimalField(
                        blank=True,
                        decimal_places=6,
                        help_text="Geographical longitude coordinate of the location for mapping (e.1g., -0.1278).",
                        max_digits=9,
                        null=True,
                    ),
                ),
                (
                    "timezone",
                    timezone_field.fields.TimeZoneField(
                        default="UTC",
                        help_text="The local timezone of the location, essential for accurate event scheduling.",
                    ),
                ),
                (
                    "phone_number",
                    phonenumber_field.modelfields.PhoneNumberField(
                        help_text="Primary contact phone number for the location (e.g., +12125550101).",
                        max_length=128,
                        region=None,
                    ),
                ),
                (
                    "email",
                    models.EmailField(
                        help_text="Primary contact email address for the location.",
                        max_length=255,
                    ),
                ),
                (
                    "website",
                    models.URLField(
                        blank=True,
                        help_text="Official website URL for this specific location, if available.",
                        max_length=255,
                        validators=[django.core.validators.URLValidator()],
                    ),
                ),
            ],
            options={
                "verbose_name": "Location",
                "verbose_name_plural": "Locations",
                "ordering": ["country", "city", "name"],
            },
            bases=(
                phoxtail.core.mixins.AdminURLMixin,
                modelsearch.index.Indexed,
                models.Model,
            ),
        ),
        migrations.CreateModel(
            name="Space",
            fields=[
                (
                    "sort_order",
                    models.IntegerField(blank=True, editable=False, null=True),
                ),
                (
                    "id",
                    models.BigAutoField(primary_key=True, serialize=False),
                ),
                (
                    "uuid",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, unique=True
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True, null=True),
                ),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "name",
                    models.CharField(
                        help_text="Descriptive name of the space (e.g., 'Conference Room A', 'Main Hall', 'Outdoor Pitch 3').",
                        max_length=100,
                    ),
                ),
                (
                    "description",
                    models.TextField(
                        blank=True,
                        help_text="Detailed description of the space, its features, and suitable uses.",
                    ),
                ),
                (
                    "capacity",
                    models.PositiveIntegerField(
                        default=0,
                        help_text="Maximum number of individuals this space can comfortably accommodate for an event.",
                    ),
                ),
                (
                    "is_active",
                    models.BooleanField(
                        default=True,
                        help_text="Indicates if this space is currently available for scheduling events.",
                    ),
                ),
                (
                    "location",
                    modelcluster.fields.ParentalKey(
                        help_text="The parent location to which this reservable space belongs.",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="spaces",
                        to="phoxtail_booking_core.location",
                    ),
                ),
            ],
            options={
                "verbose_name": "Space",
                "verbose_name_plural": "Spaces",
                "ordering": ["location__name", "name"],
                "unique_together": {("location", "name")},
            },
            bases=(
                phoxtail.core.mixins.AdminURLMixin,
                modelsearch.index.Indexed,
                models.Model,
            ),
        ),
        migrations.CreateModel(
            name="Staff",
            fields=[
                (
                    "id",
                    models.BigAutoField(primary_key=True, serialize=False),
                ),
                (
                    "uuid",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, unique=True
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True, null=True),
                ),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "bio",
                    models.TextField(
                        blank=True,
                        help_text="A brief biography or description of the staff member's role and expertise.",
                    ),
                ),
                (
                    "user",
                    models.OneToOneField(
                        help_text="The user account associated with this staff member.",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="staff",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Staff",
                "verbose_name_plural": "Staff",
            },
            bases=(
                phoxtail.core.mixins.AdminURLMixin,
                modelsearch.index.Indexed,
                models.Model,
            ),
        ),
        migrations.AddIndex(
            model_name="location",
            index=models.Index(
                fields=["latitude", "longitude"],
                name="phoxtail_bo_latitud_2644b1_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="location",
            index=models.Index(
                fields=["city", "country"],
                name="phoxtail_bo_city_c78038_idx",
            ),
        ),
    ]
