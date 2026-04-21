"""``/api/content/v1/sites/`` — Wagtail Site listing endpoint."""

from __future__ import annotations

from django.http import HttpRequest
from ninja import Router, Schema

router = Router()


class SiteSummary(Schema):
    id: int
    hostname: str
    port: int
    site_name: str
    root_page_id: int
    is_default_site: bool


class SiteList(Schema):
    sites: list[SiteSummary]
    total: int


@router.get("/", response={200: SiteList}, summary="List sites")
def list_sites(request: HttpRequest):
    from wagtail.models import Site

    qs = Site.objects.all().order_by("hostname")
    sites = [
        {
            "id": s.pk,
            "hostname": s.hostname,
            "port": s.port,
            "site_name": s.site_name,
            "root_page_id": s.root_page_id,
            "is_default_site": s.is_default_site,
        }
        for s in qs
    ]
    return {"sites": sites, "total": len(sites)}
