"""``/api/streams/v1/context`` — Assemble variant editing context.

Returns the structured data that the MCP server / CLI renders into a
context document for AI agents. The variant's own collection is always
used for design tokens — to inspect a different collection's design
system, use the collection detail endpoint instead.
"""

from __future__ import annotations

import json

from django.http import HttpRequest
from ninja import Router

from phoxtail.api.streams.v1._helpers import (
    resolve_block,
    resolve_variant,
)
from phoxtail.api.streams.v1.schemas import (
    ContextRequest,
    ContextResponse,
    Error,
)
from phoxtail.streams.models import BlockVariant, VariantCollection

router = Router()


@router.post(
    "/",
    response={200: ContextResponse, 404: Error, 409: Error},
    summary="Assemble context for AI agent editing",
)
def get_context(request: HttpRequest, payload: ContextRequest):
    """Assemble the context data needed to brief an AI agent.

    Resolves the block, the variant being edited, its collection (with
    rendered design tokens), and any reference variants. Returns
    structured data that the MCP server renders into a context document
    using its local Jinja2 template.
    """
    block = resolve_block(payload.block)
    variant = resolve_variant(payload.variant, block=payload.block)
    collection = variant.collection

    # Render the collection's design tokens template
    design_tokens = collection.render()

    # Block schema as JSON
    schema_json = json.dumps(block.schema.get_prep_value(), indent=2)

    # Reference variants
    references = _resolve_references(payload.references, collection)

    return {
        "block": {
            "identifier": block.identifier,
            "name": block.name,
            "description": block.description,
            "field_schema": schema_json,
        },
        "variant": {
            "identifier": variant.identifier,
            "name": variant.name,
            "description": variant.description,
            "html": variant.html,
            "css": variant.css,
            "javascript": variant.javascript,
        },
        "collection": {
            "identifier": collection.identifier,
            "name": collection.name,
            "description": collection.description,
            "design_tokens": design_tokens,
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


def _resolve_references(
    identifiers: list[str],
    collection: VariantCollection,
) -> list[BlockVariant]:
    if not identifiers:
        return []

    resolved: list[BlockVariant] = []
    for identifier in identifiers:
        qs = BlockVariant.objects.select_related("block", "collection").filter(
            identifier=identifier, collection=collection
        )
        matches = list(qs)
        if not matches:
            from ninja.errors import HttpError

            raise HttpError(
                404,
                f"Reference variant '{identifier}' not found in collection "
                f"'{collection.identifier}'.",
            )
        if len(matches) > 1:
            from ninja.errors import HttpError

            locations = ", ".join(
                f"{m.block.identifier}/{m.collection.identifier}" for m in matches
            )
            raise HttpError(
                409,
                f"Reference variant '{identifier}' is ambiguous within "
                f"collection '{collection.identifier}' "
                f"({len(matches)} matches: {locations}).",
            )
        resolved.append(matches[0])
    return resolved
