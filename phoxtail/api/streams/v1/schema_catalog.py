"""API endpoint for the block schema field type catalog."""

from __future__ import annotations

from typing import Any

from django.http import HttpRequest
from ninja import Router

router = Router()

# Common parameters inherited from FieldSchemaBlock that every field type has.
_COMMON_PARAM_NAMES = frozenset({"name", "required", "help_text", "icon"})

# Lazy cache — built once per process.
_catalog_cache: dict[str, Any] | None = None


def _param_info(child_block: Any) -> dict[str, Any]:
    """Extract metadata from a single Wagtail child-block definition."""
    info: dict[str, Any] = {"type": type(child_block).__name__}
    if hasattr(child_block, "required"):
        info["required"] = child_block.required
    if getattr(child_block, "help_text", ""):
        info["help_text"] = str(child_block.help_text)
    return info


def _extract_type_entry(type_id: str, block_instance: Any) -> dict[str, Any]:
    """Build a catalog entry for a single schema block type."""
    meta = getattr(block_instance, "meta", None)
    entry: dict[str, Any] = {
        "label": getattr(meta, "label", type_id),
        "icon": getattr(meta, "icon", ""),
        "group": getattr(meta, "group", ""),
        "description": (type(block_instance).__doc__ or "").strip(),
        "parameters": {},
    }
    for name, child in block_instance.child_blocks.items():
        if name not in _COMMON_PARAM_NAMES:
            entry["parameters"][name] = _param_info(child)
    return entry


def _build_common_parameters() -> dict[str, Any]:
    """Document the common parameters shared by every field type."""
    from phoxtail.streams.blocks.schema.base import FieldSchemaBlock

    base = FieldSchemaBlock()
    return {name: _param_info(child) for name, child in base.child_blocks.items()}


def _build_catalog() -> dict[str, Any]:
    """Build the complete schema field type catalog by introspection."""
    from phoxtail.streams.blocks.schema.fields import FIELD_BLOCK_CHOICES
    from phoxtail.streams.blocks.schema.layers import LAYER_BLOCK_CHOICES
    from phoxtail.streams.blocks.schema.structures import STRUCTURE_BLOCK_CHOICES

    catalog: dict[str, Any] = {
        "common_parameters": _build_common_parameters(),
        "field_types": {},
        "structure_types": {},
        "layer_types": {},
    }

    for type_id, block_inst in FIELD_BLOCK_CHOICES.choices:
        catalog["field_types"][type_id] = _extract_type_entry(type_id, block_inst)

    for type_id, block_inst in [
        STRUCTURE_BLOCK_CHOICES.STRUCT,
        STRUCTURE_BLOCK_CHOICES.LIST_FIELD,
        STRUCTURE_BLOCK_CHOICES.LIST_STRUCT,
    ]:
        catalog["structure_types"][type_id] = _extract_type_entry(type_id, block_inst)

    for type_id, block_inst in [
        LAYER_BLOCK_CHOICES.STRUCT_L1,
        LAYER_BLOCK_CHOICES.STREAM_L1,
        LAYER_BLOCK_CHOICES.LIST_STRUCT_L1,
        LAYER_BLOCK_CHOICES.STRUCT_L2,
    ]:
        entry = _extract_type_entry(type_id, block_inst)
        qualified_id = f"{type_id} ({entry['label']})"
        catalog["layer_types"][qualified_id] = entry

    return catalog


def get_schema_catalog() -> dict[str, Any]:
    """Return the schema catalog dict (lazy-built, cached)."""
    global _catalog_cache  # noqa: PLW0603
    if _catalog_cache is None:
        _catalog_cache = _build_catalog()
    return _catalog_cache


@router.get(
    "/",
    summary="Schema field type catalog",
    description=(
        "Returns the complete catalog of available schema field types "
        "and their parameters for designing block schemas."
    ),
)
def schema_catalog(request: HttpRequest):
    return get_schema_catalog()
