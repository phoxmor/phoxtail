"""``/api/streams/v1/context`` — Assemble block context for AI agents.

Returns the structured data that the MCP server / CLI renders into a
context document for AI agents. The context is scoped to a block and an
optional collection label. It does not include a specific variant, since
the agent may be creating a new one or may have fetched the variant
separately.

Design tokens (palette roles, font roles) are site-wide and always
included in the response.
"""

from __future__ import annotations

from django.http import HttpRequest

from phoxtail.api.auth import guarded
from phoxtail.api.pagination import Router
from phoxtail.design.models import FontRole, PaletteRole
from phoxtail.streams.api.v1._helpers import (
    resolve_block_by_pk,
    resolve_collection_by_pk,
)
from phoxtail.streams.api.v1.schemas import (
    ContextRequest,
    ContextResponse,
    Error,
)
from phoxtail.streams.models import BlockVariant

router = Router()


@router.post(
    "/",
    response={200: ContextResponse, 404: Error, 409: Error},
    summary="Assemble context for AI agent",
    # Two codenames, for the two things this returns that are substantive:
    # the block's field schema, and the full html, css and javascript of
    # every reference variant asked for.
    #
    # It also returns design's palette and font roles, and deliberately does
    # not name their codenames. Those rows are a vocabulary rather than data
    # — "Surface", `surface`, "used as --color-surface-{shade}" — with no
    # colour values and no font files among them, which is the same
    # character as /schema-catalog/ and gated the same way, which is to say
    # not at all. Naming them would also mean that anyone without design
    # permissions lost block context entirely, since guarded() requires all
    # of what it names.
    auth=guarded("phoxtail_streams.view_block", "phoxtail_streams.view_blockvariant"),
)
def get_context(request: HttpRequest, payload: ContextRequest):
    """Assemble the context data needed to brief an AI agent.

    Resolves the block and (optionally) the collection label, fetches
    design tokens (palette/font roles), and resolves any reference
    variants. Returns structured data that the MCP server renders into a
    context document using its local Jinja2 template.
    """
    block = resolve_block_by_pk(payload.block_id)

    collection = None
    if payload.collection_id is not None:
        collection = resolve_collection_by_pk(payload.collection_id)

    return {
        "block": block,
        "collection": collection,
        "design_tokens": {
            "palette_roles": list(PaletteRole.objects.all()),
            "font_roles": list(FontRole.objects.all()),
        },
        "references": _resolve_references(payload.references),
    }


def _resolve_references(ids: list[int]) -> list[BlockVariant]:
    if not ids:
        return []

    resolved: list[BlockVariant] = []
    for variant_id in ids:
        try:
            resolved.append(
                BlockVariant.objects.select_related("block", "collection")
                .prefetch_related("block__page_types")
                .get(pk=variant_id)
            )
        except BlockVariant.DoesNotExist:
            from ninja.errors import HttpError

            raise HttpError(404, f"Reference variant {variant_id} not found.")
    return resolved
