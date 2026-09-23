"""``/api/streams/v1/page-types`` — installed page-type app labels.

**Declares ``authenticated()`` rather than nothing.** What this returns is a
list of app labels read out of the ContentType table — no permission names
it, so there is nothing to ask for. But declaring *nothing* keeps the
API-wide default, which refuses every scoped token, and the CLI reads this
before loading a studio dump. Silence would have meant "closed"; this says
"open" out loud.
"""

from __future__ import annotations

from django.http import HttpRequest

from phoxtail.api.auth import authenticated
from phoxtail.api.pagination import Router

router = Router()


@router.get(
    "/",
    response={200: dict},
    summary="List installed page-type app labels",
    auth=authenticated(),
)
def list_page_type_app_labels(request: HttpRequest) -> dict:
    """Return the distinct app labels present in Django's ContentType table.

    The CLI uses this for pre-flight compatibility checks before loading a
    studio dump — any block whose ``page_types`` reference an app label not
    in this list will be skipped rather than sent to the API.
    """
    from django.contrib.contenttypes.models import ContentType

    app_labels = sorted(set(ContentType.objects.values_list("app_label", flat=True)))
    return {"app_labels": app_labels}
