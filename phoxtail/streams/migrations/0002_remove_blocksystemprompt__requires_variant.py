from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("phoxtail_streams", "0001_initial"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="blocksystemprompt",
            name="_requires_variant",
        ),
    ]
