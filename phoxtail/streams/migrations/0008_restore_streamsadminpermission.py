from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("phoxtail_streams", "0007_blockvariant_preview_images"),
    ]

    operations = [
        migrations.CreateModel(
            name="StreamsAdminPermission",
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
                "verbose_name": "Streams",
                "verbose_name_plural": "Streams",
                "default_permissions": (),
                "permissions": [],
            },
        ),
    ]
