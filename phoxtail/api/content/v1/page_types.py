"""``/api/content/v1/page-types/`` — discovery endpoint.

Lists every page type the contribution registry knows about, along
with its writable fields and FK-lookup tool names. The agent reads
this before writing to learn which fields exist and which MCP tool
resolves each FK to an integer ID.

Only apps installed in ``INSTALLED_APPS`` appear here — that is the
entire point of the contribution model.
"""

from __future__ import annotations

from django.http import HttpRequest
from ninja import Router

from phoxtail.api.content.v1._helpers import contribution_as_dict
from phoxtail.api.content.v1.contrib import collect_page_schemas
from phoxtail.api.content.v1.schemas import PageTypeCatalog

router = Router()


@router.get(
    "/",
    response={200: PageTypeCatalog},
    summary="List all contributed page types with their writable fields",
)
def list_page_types(request: HttpRequest):
    schemas = collect_page_schemas()
    return {"types": {content_type: contribution_as_dict(contrib) for content_type, contrib in schemas.items()}}
