import django.core.validators
import django.db.models.deletion
import django.utils.timezone
import modelcluster.fields
import modelsearch.index
import phoxtail.core.mixins
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("phoxtail_booking_core", "0001_initial"),
        ("phoxtail_booking_services", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="SubscriptionType",
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
                        help_text="Name of the subscription type (e.g., 'Monthly Unlimited', '5 Class Pack').",
                        max_length=255,
                    ),
                ),
                (
                    "description",
                    models.TextField(
                        blank=True,
                        help_text="A detailed description of the subscription benefits.",
                    ),
                ),
                (
                    "price",
                    models.DecimalField(
                        decimal_places=2,
                        help_text="The price of this subscription type.",
                        max_digits=10,
                        validators=[django.core.validators.MinValueValidator(0)],
                    ),
                ),
                (
                    "duration",
                    models.PositiveIntegerField(
                        blank=True,
                        help_text="Number of days the subscription is valid from purchase date (e.g., 30 for monthly). Leave blank for an unlimited time period (non-expiring subscription).",
                        null=True,
                    ),
                ),
                (
                    "is_active",
                    models.BooleanField(
                        default=True,
                        help_text="Indicates if this subscription type is currently available for purchase.",
                    ),
                ),
                (
                    "is_public",
                    models.BooleanField(
                        default=True,
                        help_text="Indicates if this subscription type is currently public.",
                    ),
                ),
                (
                    "credits",
                    models.PositiveIntegerField(
                        blank=True,
                        default=0,
                        help_text="Total shared credits for this subscription type.",
                        null=True,
                        validators=[django.core.validators.MinValueValidator(0)],
                    ),
                ),
                (
                    "unpaid_reservation_limit",
                    models.PositiveIntegerField(
                        default=0,
                        help_text="Number of reservations users can make before paying subscriptions of this specific subscription type.",
                        validators=[django.core.validators.MinValueValidator(0)],
                    ),
                ),
                (
                    "location",
                    models.ForeignKey(
                        help_text="The location where this subscription type is offered.",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="subscription_types",
                        to="phoxtail_booking_core.location",
                    ),
                ),
            ],
            options={
                "verbose_name": "Subscription Type",
                "verbose_name_plural": "Subscription Types",
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
            name="Subscription",
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
                    "start_date",
                    models.DateField(
                        default=django.utils.timezone.now,
                        help_text="The date this subscription became active.",
                    ),
                ),
                (
                    "end_date",
                    models.DateField(
                        blank=True,
                        help_text="The date this subscription expires. Calculated based on SubscriptionType duration.",
                        null=True,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("ACTIVE", "Active"),
                            ("FROZEN", "Frozen"),
                            ("SUSPENDED", "Suspended"),
                            ("ARCHIVED", "Archived"),
                            ("CANCELLED", "Cancelled"),
                        ],
                        default="ACTIVE",
                        help_text="Current status of the subscription (active, frozen, suspended, etc.)",
                        max_length=20,
                    ),
                ),
                (
                    "credits",
                    models.PositiveIntegerField(
                        blank=True,
                        default=0,
                        help_text="Remaining credits from shared pool for this user's subscription.",
                        null=True,
                        validators=[django.core.validators.MinValueValidator(0)],
                    ),
                ),
                (
                    "is_paid",
                    models.BooleanField(
                        default=False,
                        help_text="Indicates if this subscription has been fully paid for.",
                    ),
                ),
                (
                    "unpaid_reservation_limit",
                    models.PositiveIntegerField(
                        default=0,
                        help_text="Number of reservations this user can make before paying this subscription.",
                        validators=[django.core.validators.MinValueValidator(0)],
                    ),
                ),
                (
                    "subscription_type",
                    models.ForeignKey(
                        help_text="The type of subscription purchased.",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="subscriptions",
                        to="phoxtail_booking_subscriptions.subscriptiontype",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        help_text="The user who owns this subscription.",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="subscriptions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Subscription",
                "verbose_name_plural": "Subscriptions",
                "ordering": ["-start_date"],
            },
            bases=(
                phoxtail.core.mixins.AdminURLMixin,
                modelsearch.index.Indexed,
                models.Model,
            ),
        ),
        migrations.CreateModel(
            name="SubscriptionTypeCreditAllocation",
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
                    "credits",
                    models.PositiveIntegerField(
                        blank=True,
                        default=0,
                        help_text="Number of credits allocated for this service. Leave blank for unlimited credits.",
                        null=True,
                    ),
                ),
                (
                    "service",
                    models.ForeignKey(
                        help_text="The service these credits apply to.",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="credit_allocations",
                        to="phoxtail_booking_services.service",
                    ),
                ),
                (
                    "subscription_type",
                    modelcluster.fields.ParentalKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="credit_allocations",
                        to="phoxtail_booking_subscriptions.subscriptiontype",
                    ),
                ),
            ],
            options={
                "verbose_name": "Credit Allocation",
                "verbose_name_plural": "Credit Allocations",
                "unique_together": {("subscription_type", "service")},
            },
            bases=(
                phoxtail.core.mixins.AdminURLMixin,
                modelsearch.index.Indexed,
                models.Model,
            ),
        ),
        migrations.CreateModel(
            name="SubscriptionCreditBalance",
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
                    "credits",
                    models.PositiveIntegerField(
                        blank=True,
                        default=0,
                        help_text="Number of credits remaining for this service. Leave blank for unlimited access.",
                        null=True,
                    ),
                ),
                (
                    "service",
                    models.ForeignKey(
                        help_text="The service these credits apply to.",
                        on_delete=django.db.models.deletion.CASCADE,
                        to="phoxtail_booking_services.service",
                    ),
                ),
                (
                    "subscription",
                    modelcluster.fields.ParentalKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="credit_balances",
                        to="phoxtail_booking_subscriptions.subscription",
                    ),
                ),
            ],
            options={
                "verbose_name": "Credit Balance",
                "verbose_name_plural": "Credit Balances",
                "unique_together": {("subscription", "service")},
            },
            bases=(
                phoxtail.core.mixins.AdminURLMixin,
                modelsearch.index.Indexed,
                models.Model,
            ),
        ),
    ]
