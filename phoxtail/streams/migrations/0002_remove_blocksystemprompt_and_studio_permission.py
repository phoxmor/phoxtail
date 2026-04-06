"""Remove BlockSystemPrompt model and access_stream_studio permission.

The BlockSystemPrompt model and the Wagtail admin Studio interface have been
replaced by a static Jinja2 context template and the CLI/MCP tooling.
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("phoxtail_streams", "0001_initial"),
    ]

    operations = [
        migrations.DeleteModel(
            name="BlockSystemPrompt",
        ),
        migrations.AlterModelOptions(
            name="streamsadminpermission",
            options={
                "default_permissions": (),
                "permissions": [],
                "verbose_name": "Streams",
                "verbose_name_plural": "Streams",
            },
        ),
    ]
