# Tighten palette_set FK from nullable to non-null after the data migration
# has ensured every Palette row has a set assigned.

import django.db.models.deletion
import modelcluster.fields
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("phoxtail_design", "0003_assign_default_palette_set"),
    ]

    operations = [
        migrations.AlterField(
            model_name="palette",
            name="palette_set",
            field=modelcluster.fields.ParentalKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="palettes",
                to="phoxtail_design.paletteset",
            ),
        ),
    ]
