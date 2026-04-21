"""``/api/blog/v1/authors/`` — BlogAuthor lookup endpoint.

Read-only. Exists so an agent can resolve a human-readable author name
to the integer FK expected by ``BlogPostPage.author`` before issuing a
``PATCH /api/content/v1/pages/{id}/`` with ``{"author": <id>}``.
"""

from __future__ import annotations

from django.http import HttpRequest
from ninja import Query, Router, Schema
from wagtail.search.backends import get_search_backend

from phoxtail.blog.models import BlogAuthor

router = Router()


class AuthorItem(Schema):
    id: int
    title: str


class AuthorList(Schema):
    items: list[AuthorItem]
    total: int


@router.get(
    "/",
    response={200: AuthorList},
    summary="List/search BlogAuthor snippets",
)
def list_authors(
    request: HttpRequest,
    search: str | None = Query(
        None,
        description="Match against BlogAuthor search fields (name, email, bio).",
    ),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    qs = BlogAuthor.objects.select_related("user").all().order_by("user__username")
    if search:
        backend = get_search_backend()
        qs = backend.autocomplete(search, qs).get_queryset()

    total = qs.count()
    items = [{"id": a.pk, "title": str(a)} for a in qs[offset : offset + limit]]
    return {"items": items, "total": total}
