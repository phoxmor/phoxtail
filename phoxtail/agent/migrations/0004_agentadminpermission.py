from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("phoxtail_agent", "0003_alter_conversation_options_conversation_title"),
    ]

    operations = [
        migrations.CreateModel(
            name="AgentAdminPermission",
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
                "verbose_name": "Agent",
                "verbose_name_plural": "Agent",
                "default_permissions": (),
                "permissions": [("access_chatbot", "Can access the AI chatbot")],
            },
        ),
    ]
