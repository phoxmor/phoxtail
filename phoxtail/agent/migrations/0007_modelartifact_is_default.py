from django.db import migrations, models


def set_seeded_default(apps, schema_editor):
    ModelArtifact = apps.get_model("phoxtail_agent", "ModelArtifact")
    # Mark the bootstrapped Gemini artifact as default if no default exists yet.
    if not ModelArtifact.objects.filter(is_default=True).exists():
        ModelArtifact.objects.filter(identifier="gemini-2.5-flash").update(is_default=True)


class Migration(migrations.Migration):

    dependencies = [
        ("phoxtail_agent", "0006_seed_default_inference"),
    ]

    operations = [
        migrations.AddField(
            model_name="modelartifact",
            name="is_default",
            field=models.BooleanField(default=False),
        ),
        migrations.AddConstraint(
            model_name="modelartifact",
            constraint=models.UniqueConstraint(
                condition=models.Q(is_default=True),
                fields=["is_default"],
                name="unique_default_artifact",
            ),
        ),
        migrations.RunPython(set_seeded_default, reverse_code=migrations.RunPython.noop),
    ]
