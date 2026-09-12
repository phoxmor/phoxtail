"""StreamsSyncService — sync block variants from a Remote.

Entry points:
- StreamsSyncService(remote).pull(variant_id)  — fetch from remote → upsert locally
- StreamsSyncService(remote).push(variant_id)  — build local envelope → upsert on remote

apply_variant_envelope() is also imported by the push API endpoint on the receiving side.

Depends on phoxtail.remotes only for the Remote model (base_url + token).
All write operations target phoxtail.streams models.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import httpx
from django.apps import apps as django_apps
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import transaction

if TYPE_CHECKING:
    from phoxtail.streams.models import BlockVariant

logger = logging.getLogger(__name__)


@dataclass
class PullResult:
    variant: BlockVariant
    created: bool
    skipped_page_types: list[str] = field(default_factory=list)


@dataclass
class PushResult:
    variant_name: str
    created: bool


def apply_variant_envelope(envelope: dict) -> PullResult:
    """Upsert a BlockVariant from a sync install envelope.

    Used by StreamsSyncService.pull() (after fetching from remote) and by the
    push API endpoint on the receiving project (POST /api/streams/v1/variants/push/).
    """
    from phoxtail.streams.models import Block, BlockVariant, VariantCollection

    collection_data = envelope.get("collection")
    block_data = envelope.get("block") or {}
    variant_data = envelope.get("variant") or {}

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
        collection = None
        if collection_data and collection_data.get("identifier"):
            collection, _ = VariantCollection.objects.get_or_create(
                identifier=collection_data["identifier"],
                defaults={"name": collection_data.get("name", collection_data["identifier"])},
            )

        block, block_created = Block.objects.update_or_create(
            identifier=block_data["identifier"],
            defaults={
                "name": block_data["name"],
                "description": block_data.get("description", ""),
                "icon": block_data.get("icon", ""),
                "group": block_data.get("group", ""),
                "is_shared": block_data.get("is_shared", False),
                "site_slot": block_data.get("site_slot", ""),
                "slot_order": block_data.get("slot_order", 0),
                "render_in_preview": block_data.get("render_in_preview", True),
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
                    logger.debug("apply_variant_envelope: page_type %r not present locally, skipped", app_model)

        is_default = variant_data.get("is_default", False)
        if (
            is_default
            and block.variants.filter(is_default=True).exclude(identifier=variant_data["identifier"]).exists()
        ):
            raise ValidationError(
                f"'{block.name}' already has a default variant. "
                "Unmark the current default before pulling/pushing this one."
            )

        variant, created = BlockVariant.objects.update_or_create(
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

    return PullResult(
        variant=variant,
        created=created,
        skipped_page_types=skipped_page_types,
    )


class StreamsSyncService:
    """Capability: sync block variants from/to a connected Remote."""

    def __init__(self, remote):
        self.remote = remote

    def pull(self, variant_id: int) -> PullResult:
        url = f"{self.remote.base_url}/api/streams/v1/variants/{variant_id}/pull/"
        response = httpx.get(
            url,
            headers={"Authorization": f"Bearer {self.remote.token}"},
            timeout=15,
            follow_redirects=True,
        )
        if not response.is_success:
            raise ValidationError(f"Remote returned {response.status_code} for variant '{variant_id}'.")

        envelope = response.json().get("install") or {}
        return apply_variant_envelope(envelope)

    def push(self, variant_id: int) -> PushResult:
        from phoxtail.streams.api.v1._helpers import build_variant_envelope
        from phoxtail.streams.models import BlockVariant

        try:
            v = (
                BlockVariant.objects.select_related(
                    "block",
                    "collection",
                    "preview_image_desktop",
                    "preview_image_desktop_dark",
                    "preview_image_tablet",
                    "preview_image_tablet_dark",
                    "preview_image_mobile",
                    "preview_image_mobile_dark",
                )
                .prefetch_related("block__page_types")
                .get(pk=variant_id)
            )
        except BlockVariant.DoesNotExist:
            raise ValidationError(f"Variant {variant_id} not found.")

        envelope = build_variant_envelope(v)
        url = f"{self.remote.base_url}/api/streams/v1/variants/push/"
        response = httpx.post(
            url,
            json={"install": envelope},
            headers={"Authorization": f"Bearer {self.remote.token}"},
            timeout=15,
            follow_redirects=True,
        )
        if not response.is_success:
            try:
                detail = response.json().get("detail") or ""
            except Exception:
                detail = ""
            raise ValidationError(detail or f"Remote returned {response.status_code} while pushing variant '{v.name}'.")

        data = response.json()
        return PushResult(variant_name=data.get("name", v.name), created=data.get("created", False))
