from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("phoxtail_agent", "0001_initial"),
    ]

    operations = [
        migrations.DeleteModel(name="ToolCall"),
        migrations.DeleteModel(name="Message"),
        migrations.AddField(
            model_name="conversation",
            name="message_history",
            field=models.JSONField(default=list),
        ),
    ]
