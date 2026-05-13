"""``/api/streams/v1/context`` — Assemble block + collection context.

Returns the structured data that the MCP server / CLI renders into a
context document for AI agents. The context is scoped to a block and a
collection — it does not include a specific variant, since the agent may
be creating a new one or may have already fetched the variant separately.

Design tokens (palette roles, font roles) are site-wide and included
directly in the response.
"""

from __future__ import annotations

import json

from django.http import HttpRequest
from ninja import Router

from phoxtail.api.streams.v1._helpers import (
    resolve_block_by_pk,
    resolve_collection_by_pk,
)
from phoxtail.api.streams.v1.schemas import (
    ContextRequest,
    ContextResponse,
    Error,
)
from phoxtail.design.models import FontRole, PaletteRole
from phoxtail.streams.models import BlockVariant

router = Router()


@router.post(
    "/",
    response={200: ContextResponse, 404: Error, 409: Error},
    summary="Assemble context for AI agent",
)
def get_context(request: HttpRequest, payload: ContextRequest):
    """Assemble the context data needed to brief an AI agent.

    Resolves the block and collection, fetches design tokens
    (palette/font roles), and resolves any reference variants.
    Returns structured data that the MCP server renders into a
    context document using its local Jinja2 template.
    """
    block = resolve_block_by_pk(payload.block_id)
    collection = resolve_collection_by_pk(payload.collection_id)

    # Block schema as JSON
    schema_json = json.dumps(block.schema.get_prep_value(), indent=2)

    # Reference variants
    references = _resolve_references(payload.references)

    # Site-wide design tokens
    palette_roles = [
        {
            "name": r.name,
            "identifier": r.identifier,
            "description": r.description,
        }
        for r in PaletteRole.objects.all()
    ]
    font_roles = [
        {
            "name": r.name,
            "identifier": r.identifier,
            "description": r.description,
        }
        for r in FontRole.objects.all()
    ]

    return {
        "block": {
            "identifier": block.identifier,
            "name": block.name,
            "description": block.description,
            "field_schema": schema_json,
        },
        "collection": {
            "identifier": collection.identifier,
            "name": collection.name,
            "description": collection.description,
            "design_guidelines": collection.template,
        },
        "design_tokens": {
            "palette_roles": palette_roles,
            "font_roles": font_roles,
        },
        "references": [
            {
                "identifier": r.identifier,
                "name": r.name,
                "description": r.description,
                "html": r.html,
                "css": r.css,
                "javascript": r.javascript,
                "block": {
                    "identifier": r.block.identifier,
                    "name": r.block.name,
                },
            }
            for r in references
        ],
    }


def _resolve_references(ids: list[int]) -> list[BlockVariant]:
    if not ids:
        return []

    resolved: list[BlockVariant] = []
    for variant_id in ids:
        try:
            resolved.append(BlockVariant.objects.select_related("block", "collection").get(pk=variant_id))
        except BlockVariant.DoesNotExist:
            from ninja.errors import HttpError

            raise HttpError(404, f"Reference variant {variant_id} not found.")
    return resolved
