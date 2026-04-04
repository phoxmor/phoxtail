import django.db.models.deletion
import modelsearch.index
import phoxtail.core.mixins
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("phoxtail_design", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Service",
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
                        help_text="Name of the specific service offering (e.g., 'Pilates Mat Class', 'Reformer Session').",
                        max_length=255,
                        unique=True,
                    ),
                ),
                (
                    "description",
                    models.TextField(
                        blank=True,
                        help_text="A brief description of what this service entails.",
                    ),
                ),
                (
                    "is_active",
                    models.BooleanField(
                        default=True,
                        help_text="Indicates if this service offering is currently available.",
                    ),
                ),
                (
                    "cancellation_lockout_hours",
                    models.PositiveIntegerField(
                        default=1,
                        help_text="Number of hours before the event start time after which cancellations are not allowed.",
                    ),
                ),
                (
                    "palette",
                    models.ForeignKey(
                        blank=True,
                        help_text="Select a color palette for the service",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="services",
                        to="phoxtail_design.palette",
                    ),
                ),
            ],
            options={
                "verbose_name": "Service",
                "verbose_name_plural": "Services",
                "ordering": ["name"],
            },
            bases=(
                phoxtail.core.mixins.AdminURLMixin,
                modelsearch.index.Indexed,
                models.Model,
            ),
        ),
    ]
