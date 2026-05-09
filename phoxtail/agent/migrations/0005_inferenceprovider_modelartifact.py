import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
        ("phoxtail_agent", "0004_agentadminpermission"),
    ]

    operations = [
        migrations.CreateModel(
            name="InferenceProvider",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("uuid", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, null=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("identifier", models.SlugField(unique=True)),
                ("display_name", models.CharField(max_length=100)),
                ("model_prefix", models.CharField(blank=True, max_length=64)),
                ("base_url", models.URLField(blank=True)),
                ("api_key_env_var", models.CharField(blank=True, max_length=200)),
                ("is_active", models.BooleanField(default=True)),
            ],
            options={
                "ordering": ["display_name"],
            },
        ),
        migrations.CreateModel(
            name="ModelArtifact",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("uuid", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, null=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("sort_order", models.IntegerField(blank=True, editable=False, null=True)),
                ("identifier", models.CharField(max_length=200)),
                ("display_name", models.CharField(max_length=100)),
                ("is_active", models.BooleanField(default=True)),
                (
                    "permission",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to="auth.permission",
                    ),
                ),
                (
                    "provider",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="artifacts",
                        to="phoxtail_agent.inferenceprovider",
                    ),
                ),
            ],
            options={
                "ordering": ["sort_order"],
                "unique_together": {("provider", "identifier")},
            },
        ),
        migrations.AddField(
            model_name="conversation",
            name="last_artifact_used",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to="phoxtail_agent.modelartifact",
            ),
        ),
    ]
