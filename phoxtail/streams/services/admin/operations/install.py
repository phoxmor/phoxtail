"""RegistryServiceAdminInstall — pull one block variant from a connected registry.

Fetches the catalog detail endpoint, then resolves Block / VariantCollection /
BlockVariant via get_or_create (keyed on identifier). Idempotent: calling twice
for the same variant is safe and returns created=False on the second call.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import httpx
from django.contrib.contenttypes.models import ContentType
from django.db import transaction

logger = logging.getLogger(__name__)


@dataclass
class InstallResult:
    variant: object
    created: bool
    skipped_page_types: list[str] = field(default_factory=list)


class RegistryServiceAdminInstall:
    def __init__(self, service):
        self.service = service

    def authorize(self):
        pass

    def validate(self, variant_slug: str):
        pass

    def perform(self, registry, variant_slug: str) -> InstallResult:
        from phoxtail.streams.models import Block, BlockVariant, VariantCollection

        url = f"{registry.base_url}/api/registry/v1/catalog/variants/{variant_slug}/"
        response = httpx.get(
            url,
            headers={"Authorization": f"Bearer {registry.token}"},
            timeout=15,
            follow_redirects=True,
        )
        if not response.is_success:
            from django.core.exceptions import ValidationError

            raise ValidationError(f"Registry returned {response.status_code} for variant '{variant_slug}'.")

        install = response.json().get("install") or {}
        collection_data = install.get("collection") or {}
        block_data = install.get("block") or {}
        variant_data = install.get("variant") or {}

        with transaction.atomic():
            collection, _ = VariantCollection.objects.get_or_create(
                identifier=collection_data["identifier"],
                defaults={"name": collection_data["name"]},
            )

            block, block_created = Block.objects.get_or_create(
                identifier=block_data["identifier"],
                defaults={
                    "name": block_data["name"],
                    "description": "",
                    "source_app": block_data.get("source_app", ""),
                    "schema": block_data.get("schema_json") or [],
                },
            )

            skipped_page_types: list[str] = []
            if block_created and block_data.get("page_types"):
                for app_model in block_data["page_types"]:
                    try:
                        app_label, model_name = app_model.rsplit(".", 1)
                        ct = ContentType.objects.get(app_label=app_label, model=model_name.lower())
                        block.page_types.add(ct)
                    except (ValueError, ContentType.DoesNotExist):
                        skipped_page_types.append(app_model)
                        logger.debug("install: page_type %r not present locally, skipped", app_model)

            variant, created = BlockVariant.objects.get_or_create(
                block=block,
                collection=collection,
                identifier=variant_data["identifier"],
                defaults={
                    "name": variant_data["name"],
                    "description": "",
                    "html": variant_data.get("html", ""),
                    "css": variant_data.get("css", ""),
                    "javascript": variant_data.get("js", ""),
                },
            )

        return InstallResult(variant=variant, created=created, skipped_page_types=skipped_page_types)

    def execute(self, variant_slug: str) -> InstallResult:
        registry = self.service.registry
        self.authorize()
        self.validate(variant_slug=variant_slug)
        return self.perform(registry=registry, variant_slug=variant_slug)
