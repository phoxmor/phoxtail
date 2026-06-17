import uuid

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Remote",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("uuid", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, null=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "name",
                    models.CharField(
                        max_length=100,
                        unique=True,
                        help_text="Display label for this remote (e.g. 'Phoxtail Registry').",
                    ),
                ),
                (
                    "base_url",
                    models.URLField(
                        unique=True,
                        help_text="Root URL of the remote project, e.g. https://registry.phoxtail.com — no trailing slash.",
                    ),
                ),
                (
                    "token",
                    models.CharField(
                        help_text="Bearer token for this remote. Never displayed after save.",
                        max_length=200,
                    ),
                ),
            ],
            options={
                "verbose_name": "Remote",
                "verbose_name_plural": "Remotes",
                "ordering": ["name"],
            },
        ),
        migrations.CreateModel(
            name="RemotesAdminPermission",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ],
            options={
                "verbose_name": "Remotes",
                "verbose_name_plural": "Remotes",
                "permissions": [("manage_remotes", "Can manage remotes")],
                "default_permissions": (),
            },
        ),
    ]
