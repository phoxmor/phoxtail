"""Page-schema contribution for ``phoxtail.cms.SitePage``.

SitePage is always present in a hatched project (the ``phoxtail.cms``
app is not optional), so its contribution is the minimum a project
exposes over the pages API when no other apps contribute.
"""

from __future__ import annotations

from typing import Any

from phoxtail.cms.api.v1._helpers import serialize_body
from phoxtail.cms.api.v1.contrib import PageSchemaContribution
from phoxtail.cms.models import SitePage


def _serialize_site_page(page: SitePage) -> dict[str, Any]:
    return {"body": serialize_body(page)}


def _apply_site_page_patch(page: SitePage, data: dict[str, Any]) -> None:
    # SitePage has no scalar per-type writable fields beyond the
    # common ones — the body is written via PUT /pages/{id}/body/.
    return None


def contribute_site_page() -> PageSchemaContribution:
    return PageSchemaContribution(
        model=SitePage,
        content_type="phoxtail_cms.sitepage",
        writable_fields={
            "body": {
                "type": "list[StreamBlock]",
                "required": False,
                "writable_via": "phoxtail_pages_replace_body",
            },
        },
        serialize=_serialize_site_page,
        apply_patch=_apply_site_page_patch,
        fk_lookups={},
    )
