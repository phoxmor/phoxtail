"""``/api/streams/v1/prompts`` — BlockSystemPrompt endpoints.

Includes the prompt-rendering action that replaces the Wagtail-admin
Studio "copy to clipboard" workflow. The action reuses
``BlockSystemPrompt.render()`` unchanged.
"""

from __future__ import annotations

from django.http import HttpRequest
from ninja import Router
from ninja.errors import HttpError

from phoxtail.api.streams.v1._helpers import (
    prompt_detail,
    prompt_summary,
    resolve_collection,
    resolve_prompt,
    resolve_variant,
    variant_summary,
)
from phoxtail.api.streams.v1.schemas import (
    Error,
    Prompt,
    PromptList,
    PromptRenderRequest,
    PromptRenderResponse,
)
from phoxtail.streams.models import BlockSystemPrompt, BlockVariant, VariantCollection

router = Router()


@router.get("/", response={200: PromptList}, summary="List BlockSystemPrompts")
def list_prompts(request: HttpRequest):
    qs = BlockSystemPrompt.objects.all().order_by("name")
    prompts = [prompt_summary(p) for p in qs]
    return {"prompts": prompts, "total": len(prompts)}


@router.get(
    "/{identifier}/",
    response={200: Prompt, 404: Error},
    summary="Show a BlockSystemPrompt",
)
def get_prompt(request: HttpRequest, identifier: str):
    p = resolve_prompt(identifier)
    return prompt_detail(p)


@router.post(
    "/{identifier}/render/",
    response={200: PromptRenderResponse, 404: Error, 409: Error},
    summary="Render a system prompt for a variant",
)
def render_prompt(
    request: HttpRequest,
    identifier: str,
    payload: PromptRenderRequest,
):
    """Render a ``BlockSystemPrompt`` for a variant.

    Reuses ``BlockSystemPrompt.render()`` unchanged, so the output is
    byte-identical to what the Wagtail-admin Studio's "copy prompt" flow
    produced for equivalent inputs.
    """
    prompt = resolve_prompt(identifier)
    variant = resolve_variant(
        payload.variant, block=payload.block, collection=payload.collection
    )
    collection = (
        resolve_collection(payload.collection)
        if payload.collection
        else variant.collection
    )
    references = _resolve_references(
        payload.references, collection=collection, current_variant=variant
    )

    rendered = prompt.render(
        variant=variant,
        collection=collection,
        references=references,
    )

    return {
        "prompt": rendered,
        "template": prompt_summary(prompt),
        "variant": variant_summary(variant),
        "collection": {
            "identifier": collection.identifier,
            "name": collection.name,
        },
        "references": [variant_summary(r) for r in references],
    }


def _resolve_references(
    identifiers: list[str],
    collection: VariantCollection,
    current_variant: BlockVariant,
) -> list[BlockVariant]:
    if not identifiers:
        return []

    resolved: list[BlockVariant] = []
    for identifier in identifiers:
        qs = (
            BlockVariant.objects.select_related("block", "collection")
            .filter(identifier=identifier, collection=collection)
            .exclude(pk=current_variant.pk)
        )
        matches = list(qs)
        if not matches:
            raise HttpError(
                404,
                f"Reference variant '{identifier}' not found in collection "
                f"'{collection.identifier}'.",
            )
        if len(matches) > 1:
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
