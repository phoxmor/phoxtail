"""``/api/cms/v1/page-types/`` — discovery endpoint.

Lists every page type the contribution registry knows about, along
with its writable fields and FK-lookup tool names. The agent reads
this before writing to learn which fields exist and which MCP tool
resolves each FK to an integer ID.

Only apps installed in ``INSTALLED_APPS`` appear here — that is the
entire point of the contribution model.

**Deliberately asks for nothing, and says so.** What this returns is
derived from installed code, not from rows: page type names, field names,
their types and which are required. There is no ``PageType`` model and no
permission naming it, so there is nothing to ask for. The content behind
those types is a separate question, asked by the pages endpoints, which
answer it per subtree.

It carries ``authenticated()`` rather than no annotation at all, and the
distinction is the whole point. An endpoint with no ``auth=`` keeps the
API-wide default, which *refuses a scoped token* — so leaving this bare
would mean a token narrowed to ``add_page`` could not read the field list
it needs before creating a page, and the discovery step of every agent
page workflow would fail for exactly the credentials scopes exist to
make useful. Declaring nothing closes a door; this says the door is open.
"""

from __future__ import annotations

from django.http import HttpRequest

from phoxtail.api.auth import authenticated
from phoxtail.api.pagination import Router
from phoxtail.cms.api.v1._helpers import contribution_as_dict
from phoxtail.cms.api.v1.contrib import collect_page_schemas
from phoxtail.cms.api.v1.schemas import PageTypeCatalog

router = Router()


@router.get(
    "/",
    response={200: PageTypeCatalog},
    summary="List all contributed page types with their writable fields",
    auth=authenticated(),
)
def list_page_types(request: HttpRequest):
    schemas = collect_page_schemas()
    return {"types": {content_type: contribution_as_dict(contrib) for content_type, contrib in schemas.items()}}
