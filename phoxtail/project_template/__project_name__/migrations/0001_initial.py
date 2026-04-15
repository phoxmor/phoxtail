import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("phoxtail_cms", "0001_initial"),
        ("phoxtail_streams", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="ContentPage",
            fields=[
                (
                    "sitepage_ptr",
                    models.OneToOneField(
                        auto_created=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        parent_link=True,
                        primary_key=True,
                        serialize=False,
                        to="phoxtail_cms.sitepage",
                    ),
                ),
            ],
            options={
                "verbose_name": "Page",
                "verbose_name_plural": "Pages",
            },
            bases=("phoxtail_cms.sitepage",),
        ),
    ]
