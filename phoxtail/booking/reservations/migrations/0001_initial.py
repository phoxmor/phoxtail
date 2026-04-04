import django.db.models.deletion
import modelsearch.index
import phoxtail.core.mixins
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("phoxtail_booking_events", "0001_initial"),
        ("phoxtail_booking_subscriptions", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Reservation",
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
                    "status",
                    models.CharField(
                        choices=[
                            ("COMPLETED", "Completed"),
                            ("CONFIRMED", "Confirmed"),
                            ("CANCELLED", "Cancelled"),
                            ("WAITLISTED", "Waitlisted"),
                            ("NO_SHOW", "No Show"),
                        ],
                        default="CONFIRMED",
                        help_text="Current status of the reservation (e.g., Confirmed, Cancelled, Waitlisted).",
                        max_length=20,
                    ),
                ),
                (
                    "notes",
                    models.TextField(
                        blank=True,
                        help_text="Any private notes for this reservation.",
                    ),
                ),
                (
                    "event",
                    models.ForeignKey(
                        help_text="The specific event being reserved.",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="reservations",
                        to="phoxtail_booking_events.event",
                    ),
                ),
                (
                    "subscription",
                    models.ForeignKey(
                        help_text="The user subscription used for this reservation.",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="reservations",
                        to="phoxtail_booking_subscriptions.subscription",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        help_text="The user who made the reservation.",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="reservations",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Reservation",
                "verbose_name_plural": "Reservations",
                "unique_together": {("user", "event")},
            },
            bases=(
                phoxtail.core.mixins.AdminURLMixin,
                modelsearch.index.Indexed,
                models.Model,
            ),
        ),
    ]
