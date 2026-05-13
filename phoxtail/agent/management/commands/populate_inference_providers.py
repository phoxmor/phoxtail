"""
Populate InferenceProvider and ModelArtifact records for Google Gemini and Anthropic.

Idempotent — safe to re-run on an already-migrated database. The seed migration
(0006) may have already created the google-gemini provider and gemini-2.5-flash;
this command expands that with the full model catalogue and adds Anthropic.

Usage:
    python manage.py populate_inference_providers
    python manage.py populate_inference_providers --only=google
    python manage.py populate_inference_providers --only=anthropic
"""

from django.core.management.base import BaseCommand

PROVIDERS = [
    {
        "identifier": "google-gemini",
        "display_name": "Google Gemini",
        "model_prefix": "google-gla",
        "base_url": "",
        "api_key_env_var": "GEMINI_API_KEY",
        "artifacts": [
            {
                "identifier": "gemini-3.1-pro-preview",
                "display_name": "Gemini 3.1 Pro (Preview)",
                "sort_order": 0,
            },
            {
                "identifier": "gemini-3-flash-preview",
                "display_name": "Gemini 3 Flash (Preview)",
                "sort_order": 1,
            },
            {
                "identifier": "gemini-3.1-flash-lite",
                "display_name": "Gemini 3.1 Flash-Lite",
                "sort_order": 2,
            },
            {
                "identifier": "gemini-2.5-pro",
                "display_name": "Gemini 2.5 Pro",
                "sort_order": 3,
            },
            {
                "identifier": "gemini-2.5-flash",
                "display_name": "Gemini 2.5 Flash",
                "sort_order": 4,
            },
            {
                "identifier": "gemini-2.5-flash-lite",
                "display_name": "Gemini 2.5 Flash-Lite",
                "sort_order": 5,
            },
        ],
    },
    {
        "identifier": "anthropic",
        "display_name": "Anthropic",
        "model_prefix": "anthropic",
        "base_url": "",
        "api_key_env_var": "ANTHROPIC_API_KEY",
        "artifacts": [
            {
                "identifier": "claude-opus-4-7",
                "display_name": "Claude Opus 4.7",
                "sort_order": 10,
            },
            {
                "identifier": "claude-sonnet-4-6",
                "display_name": "Claude Sonnet 4.6",
                "sort_order": 11,
            },
            {
                "identifier": "claude-haiku-4-5-20251001",
                "display_name": "Claude Haiku 4.5",
                "sort_order": 12,
            },
        ],
    },
]


class Command(BaseCommand):
    help = "Populate InferenceProvider and ModelArtifact records for Google and Anthropic"  # noqa: E501

    def add_arguments(self, parser):
        parser.add_argument(
            "--only",
            choices=["google", "anthropic", "all"],
            default="all",
            help="Restrict to a single provider family",
        )

    def handle(self, *args, **options):
        from phoxtail.agent.models import InferenceProvider, ModelArtifact

        only = options["only"]
        _slug_map = {"google": "google-gemini", "anthropic": "anthropic"}
        provider_filter = _slug_map.get(only)

        total_providers_created = 0
        total_providers_updated = 0
        total_artifacts_created = 0
        total_artifacts_updated = 0

        for pdata in PROVIDERS:
            if provider_filter and pdata["identifier"] != provider_filter:
                continue

            provider, p_created = InferenceProvider.objects.update_or_create(
                identifier=pdata["identifier"],
                defaults={
                    "display_name": pdata["display_name"],
                    "model_prefix": pdata["model_prefix"],
                    "base_url": pdata["base_url"],
                    "api_key_env_var": pdata["api_key_env_var"],
                    "is_active": True,
                },
            )

            if p_created:
                self.stdout.write(self.style.SUCCESS(f"  Created provider: {provider.display_name}"))
                total_providers_created += 1
            else:
                self.stdout.write(f"  Updated provider: {provider.display_name}")
                total_providers_updated += 1

            for adata in pdata["artifacts"]:
                mutable = {
                    "display_name": adata["display_name"],
                    "sort_order": adata["sort_order"],
                    "is_active": True,
                }
                artifact, a_created = ModelArtifact.objects.get_or_create(
                    provider=provider,
                    identifier=adata["identifier"],
                    defaults=mutable,
                )
                if not a_created:
                    for k, v in mutable.items():
                        setattr(artifact, k, v)
                    artifact.save(update_fields=list(mutable.keys()))
                label = f"{artifact.display_name} ({artifact.identifier})"
                if a_created:
                    self.stdout.write(self.style.SUCCESS(f"    Created: {label}"))
                    total_artifacts_created += 1
                else:
                    self.stdout.write(f"    Updated: {label}")
                    total_artifacts_updated += 1

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(f"Providers: {total_providers_created} created, {total_providers_updated} updated")
        )
        self.stdout.write(
            self.style.SUCCESS(f"Artifacts: {total_artifacts_created} created, {total_artifacts_updated} updated")
        )
