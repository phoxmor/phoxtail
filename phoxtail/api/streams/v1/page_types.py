"""``/api/streams/v1/page-types`` — installed page-type app labels."""

from __future__ import annotations

from django.http import HttpRequest
from ninja import Router

router = Router()


@router.get(
    "/",
    response={200: dict},
    summary="List installed page-type app labels",
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
