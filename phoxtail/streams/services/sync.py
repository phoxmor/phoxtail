"""StreamsSyncService — sync block variants from a Remote.

Entry point: StreamsSyncService(remote).install(variant_id=<int>)

Depends on phoxtail.remotes only for the Remote model (base_url + token).
All write operations target phoxtail.streams models.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import httpx
from django.apps import apps as django_apps
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import transaction

logger = logging.getLogger(__name__)


@dataclass
class InstallResult:
    variant: object
    created: bool
    skipped_page_types: list[str] = field(default_factory=list)


class StreamsSyncService:
    """Capability: sync block variants from a connected Remote."""

    def __init__(self, remote):
        self.remote = remote

    def install(self, variant_id: int) -> InstallResult:
        from phoxtail.streams.models import Block, BlockVariant, VariantCollection

        url = f"{self.remote.base_url}/api/registry/v1/streams/variants/{variant_id}/"
        response = httpx.get(
            url,
            headers={"Authorization": f"Bearer {self.remote.token}"},
            timeout=15,
            follow_redirects=True,
        )
        if not response.is_success:
            raise ValidationError(f"Remote returned {response.status_code} for variant '{variant_id}'.")

        install = response.json().get("install") or {}
        collection_data = install.get("collection") or {}
        block_data = install.get("block") or {}
        variant_data = install.get("variant") or {}

        local_app_labels = {ac.label for ac in django_apps.get_app_configs()}
        block_name = block_data.get("name") or block_data.get("identifier", "unknown")

        source_app = block_data.get("source_app", "")
        if source_app and source_app not in local_app_labels:
            raise ValidationError(
                f"Block '{block_name}' requires app '{source_app}' which is not installed in this project."
            )

        page_type_app_labels = {
            app_model.rsplit(".", 1)[0] for app_model in block_data.get("page_types", []) if "." in app_model
        }
        missing_apps = page_type_app_labels - local_app_labels
        if missing_apps:
            raise ValidationError(
                f"Block '{block_name}' targets page types from apps not installed in this project: "
                + ", ".join(sorted(missing_apps))
                + "."
            )

        with transaction.atomic():
            collection, _ = VariantCollection.objects.get_or_create(
                identifier=collection_data["identifier"],
                defaults={"name": collection_data["name"]},
            )

            block, block_created = Block.objects.get_or_create(
                identifier=block_data["identifier"],
                defaults={
                    "name": block_data["name"],
                    "description": block_data.get("description", ""),
                    "is_shared": block_data.get("is_shared", False),
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

            is_default = variant_data.get("is_default", False)
            if (
                is_default
                and block.variants.filter(is_default=True).exclude(identifier=variant_data["identifier"]).exists()
            ):
                raise ValidationError(
                    f"'{block.name}' already has a default variant. "
                    "Unmark the current default before installing this one."
                )

            variant, created = BlockVariant.objects.get_or_create(
                block=block,
                collection=collection,
                identifier=variant_data["identifier"],
                defaults={
                    "name": variant_data["name"],
                    "description": variant_data.get("description", ""),
                    "is_default": is_default,
                    "html": variant_data.get("html", ""),
                    "css": variant_data.get("css", ""),
                    "javascript": variant_data.get("js", ""),
                },
            )

        return InstallResult(variant=variant, created=created, skipped_page_types=skipped_page_types)
