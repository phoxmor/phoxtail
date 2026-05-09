from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("phoxtail_agent", "0008_agentsettings"),
    ]

    operations = [
        migrations.RenameModel(
            old_name="AgentSettings",
            new_name="AgentSiteSetting",
        ),
        migrations.AlterModelOptions(
            name="agentsitesetting",
            options={"verbose_name": "Agent"},
        ),
    ]
