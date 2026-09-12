"""``/api/cms/v1/locales/`` — Wagtail Locale listing endpoint."""

from __future__ import annotations

from django.http import HttpRequest
from ninja import Router, Schema

router = Router()


class LocaleSummary(Schema):
    id: int
    language_code: str


class LocaleList(Schema):
    locales: list[LocaleSummary]
    total: int


@router.get("/", response={200: LocaleList}, summary="List locales")
def list_locales(request: HttpRequest):
    from wagtail.models import Locale

    qs = Locale.objects.all().order_by("language_code")
    locales = [{"id": loc.pk, "language_code": loc.language_code} for loc in qs]
    return {"locales": locales, "total": len(locales)}
