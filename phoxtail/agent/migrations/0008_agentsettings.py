import django.db.models.deletion
from django.db import migrations, models


def migrate_default_artifact(apps, schema_editor):
    """Copy is_default=True artifact → AgentSettings.default_artifact for the default site."""
    ModelArtifact = apps.get_model("phoxtail_agent", "ModelArtifact")
    AgentSettings = apps.get_model("phoxtail_agent", "AgentSettings")
    Site = apps.get_model("wagtailcore", "Site")

    default_artifact = ModelArtifact.objects.filter(is_default=True).first()
    if default_artifact is None:
        return

    try:
        site = Site.objects.get(is_default_site=True)
    except Site.DoesNotExist:
        site = Site.objects.first()

    if site is None:
        return

    AgentSettings.objects.update_or_create(
        site=site,
        defaults={"default_artifact_id": default_artifact.pk},
    )


class Migration(migrations.Migration):

    dependencies = [
        ("phoxtail_agent", "0007_modelartifact_is_default"),
        ("wagtailcore", "0096_referenceindex_referenceindex_source_object_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="AgentSettings",
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
                (
                    "site",
                    models.OneToOneField(
                        editable=False,
                        on_delete=django.db.models.deletion.CASCADE,
                        to="wagtailcore.site",
                    ),
                ),
                (
                    "default_artifact",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to="phoxtail_agent.modelartifact",
                    ),
                ),
            ],
            options={
                "verbose_name": "Agent settings",
            },
        ),
        migrations.RunPython(
            migrate_default_artifact,
            reverse_code=migrations.RunPython.noop,
        ),
        migrations.RemoveConstraint(
            model_name="modelartifact",
            name="unique_default_artifact",
        ),
        migrations.RemoveField(
            model_name="modelartifact",
            name="is_default",
        ),
    ]
