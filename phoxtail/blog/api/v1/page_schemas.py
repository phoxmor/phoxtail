"""Page-schema contributions for blog page types.

Each ``contribute_*`` callable is declared on
``PhoxtailBlogConfig.page_schema_contributors`` and collected by
``phoxtail.api.content.v1.contrib.collect_page_schemas()``.

Contributions are explicit: writable fields are listed by hand, and
``serialize`` / ``apply_patch`` callables are shipped alongside the
metadata. No introspection.
"""

from __future__ import annotations

from typing import Any

from django.conf import settings

from phoxtail.api.content.v1._helpers import serialize_body
from phoxtail.api.content.v1.contrib import PageSchemaContribution
from phoxtail.blog.models import BlogAuthor, BlogIndexPage, BlogPostPage

# ---------------------------------------------------------------------------
# BlogPostPage
# ---------------------------------------------------------------------------


def _serialize_blog_post(page: BlogPostPage) -> dict[str, Any]:
    return {
        "intro": page.intro or "",
        "read_mins": page.read_mins,
        "author": page.author_id,
        "preview_image": page.preview_image_id,
        "tags": sorted(t.name for t in page.tags.all()),
        "hide_dates": page.hide_dates,
        "first_published_at_override": page.first_published_at_override,
        "last_published_at_override": page.last_published_at_override,
        "body": serialize_body(page),
    }


def _apply_blog_post_patch(page: BlogPostPage, data: dict[str, Any]) -> None:
    if "intro" in data:
        page.intro = data["intro"]
    if "read_mins" in data:
        page.read_mins = data["read_mins"]
    if "author" in data:
        page.author = _resolve_author(data["author"])
    if "preview_image" in data:
        page.preview_image_id = data["preview_image"]
    if "hide_dates" in data:
        page.hide_dates = bool(data["hide_dates"])
    if "first_published_at_override" in data:
        page.first_published_at_override = data["first_published_at_override"]
    if "last_published_at_override" in data:
        page.last_published_at_override = data["last_published_at_override"]
    if "tags" in data:
        _apply_tags(page, data["tags"] or [])


def _resolve_author(value: Any) -> BlogAuthor | None:
    if value in (None, "", 0):
        return None
    try:
        return BlogAuthor.objects.get(pk=int(value))
    except (BlogAuthor.DoesNotExist, ValueError, TypeError) as exc:
        from ninja.errors import HttpError

        raise HttpError(400, f"Unknown BlogAuthor id: {value!r}.") from exc


def _apply_tags(page: BlogPostPage, tag_names: list[str]) -> None:
    # django-taggit ≥ 4 takes a single positional iterable (not *args).
    # ``clear=True`` replaces the existing tag set wholesale.
    names = [str(n).strip() for n in tag_names if str(n).strip()]
    page.tags.set(names, clear=True)


def contribute_blog_post() -> PageSchemaContribution:
    return PageSchemaContribution(
        model=BlogPostPage,
        content_type="phoxtail_blog.blogpostpage",
        writable_fields={
            "intro": {"type": "str", "required": False},
            "read_mins": {"type": "int", "required": False},
            "author": {
                "type": "int",
                "required": False,
                "fk_model": "phoxtail_blog.BlogAuthor",
            },
            "preview_image": {
                "type": "int",
                "required": False,
                "fk_model": settings.WAGTAILIMAGES_IMAGE_MODEL,
            },
            "tags": {"type": "list[str]", "required": False},
            "hide_dates": {"type": "bool", "required": False},
            "first_published_at_override": {
                "type": "datetime|null",
                "required": False,
            },
            "last_published_at_override": {
                "type": "datetime|null",
                "required": False,
            },
            "body": {
                "type": "list[StreamBlock]",
                "required": False,
                "writable_via": "phoxtail_pages_replace_body",
            },
        },
        serialize=_serialize_blog_post,
        apply_patch=_apply_blog_post_patch,
        fk_lookups={
            "author": "phoxtail_blog_list_authors",
            "preview_image": "phoxtail_pages_list_images",
        },
    )


# ---------------------------------------------------------------------------
# BlogIndexPage
# ---------------------------------------------------------------------------


def _serialize_blog_index(page: BlogIndexPage) -> dict[str, Any]:
    return {
        "posts_per_page": page.posts_per_page,
        "body": serialize_body(page),
    }


def _apply_blog_index_patch(page: BlogIndexPage, data: dict[str, Any]) -> None:
    if "posts_per_page" in data:
        page.posts_per_page = int(data["posts_per_page"])


def contribute_blog_index() -> PageSchemaContribution:
    return PageSchemaContribution(
        model=BlogIndexPage,
        content_type="phoxtail_blog.blogindexpage",
        writable_fields={
            "posts_per_page": {"type": "int", "required": False},
            "body": {
                "type": "list[StreamBlock]",
                "required": False,
                "writable_via": "phoxtail_pages_replace_body",
            },
        },
        serialize=_serialize_blog_index,
        apply_patch=_apply_blog_index_patch,
        fk_lookups={},
    )
