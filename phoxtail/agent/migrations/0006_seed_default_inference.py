from django.db import migrations


def seed_default(apps, schema_editor):
    InferenceProvider = apps.get_model("phoxtail_agent", "InferenceProvider")
    ModelArtifact = apps.get_model("phoxtail_agent", "ModelArtifact")

    if InferenceProvider.objects.exists():
        return

    provider = InferenceProvider.objects.create(
        identifier="google-gemini",
        display_name="Google Gemini",
        model_prefix="google-gla",
        api_key_env_var="GEMINI_API_KEY",
    )
    ModelArtifact.objects.create(
        provider=provider,
        identifier="gemini-2.5-flash",
        display_name="Gemini 2.5 Flash",
        sort_order=1,
    )


def unseed_default(apps, schema_editor):
    InferenceProvider = apps.get_model("phoxtail_agent", "InferenceProvider")
    InferenceProvider.objects.filter(identifier="google-gemini").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("phoxtail_agent", "0005_inferenceprovider_modelartifact"),
    ]

    operations = [
        migrations.RunPython(seed_default, reverse_code=unseed_default),
    ]
