"""``/api/cms/v1/locales/`` — Wagtail Locale listing endpoint."""

from __future__ import annotations

from django.http import HttpRequest
from ninja import Schema

from phoxtail.api.auth import guarded
from phoxtail.api.pagination import Router

router = Router()


class LocaleSummary(Schema):
    id: int
    language_code: str


@router.get(
    "/",
    response={200: list[LocaleSummary]},
    summary="List locales",
    auth=guarded("wagtailcore.view_locale"),
)
def list_locales(request: HttpRequest):
    from wagtail.models import Locale

    return Locale.objects.order_by("language_code")
