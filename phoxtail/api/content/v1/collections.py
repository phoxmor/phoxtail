"""``/api/content/v1/collections/`` — Wagtail Collection CRUD.

Collections form a tree (treebeard MP_Node). The root node (depth=1) is
Wagtail-managed and included in list/get responses so that agents can
reference its id when creating top-level collections or moving media
to the top level.

Endpoints:
- GET    /              — list all collections (root included, flat)
- POST   /              — create under parent_id (default: root)
- GET    /{id}/         — detail with ETag
- PATCH  /{id}/         — rename and/or reparent (If-Match required)
- DELETE /{id}/         — refuse (409) if non-empty, require If-Match
"""

from __future__ import annotations

import hashlib

from django.contrib.auth.models import Group
from django.db import transaction
from django.http import HttpRequest, HttpResponse
from ninja import Router, Schema
from ninja.errors import HttpError

router = Router()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class ViewRestrictionDetail(Schema):
    type: str  # "none", "password", "login", "groups"
    password: str | None = None
    groups: list[dict] = []  # [{"id": int, "name": str}]


class CollectionItem(Schema):
    id: int
    name: str
    depth: int
    parent_id: int | None = None
    view_restriction: ViewRestrictionDetail | None = None


class CollectionList(Schema):
    items: list[CollectionItem]
    total: int


class ViewRestrictionWrite(Schema):
    type: str  # "none", "password", "login", "groups"
    password: str | None = None
    groups: list[int] = []  # group PKs


class CollectionCreate(Schema):
    name: str
    parent_id: int | None = None  # None = direct child of root
    view_restriction: ViewRestrictionWrite | None = None


class CollectionPatch(Schema):
    name: str | None = None
    parent_id: int | None = None  # if present in payload, reparent
    view_restriction: ViewRestrictionWrite | None = None


class Error(Schema):
    detail: str


# ---------------------------------------------------------------------------
# ETag helpers
# ---------------------------------------------------------------------------


def _collection_etag(c, restriction=None) -> str:
    if restriction is None:
        from wagtail.models import CollectionViewRestriction

        restriction = CollectionViewRestriction.objects.filter(collection=c).first()
    h = hashlib.sha256()
    for part in [
        str(c.pk),
        c.name,
        c.path,
        restriction.restriction_type if restriction else "none",
        restriction.password if restriction else "",
    ]:
        h.update(part.encode())
        h.update(b"\x00")
    return f'W/"{h.hexdigest()[:16]}"'


def _strip_weak(tag: str) -> str:
    return tag[2:] if tag.startswith("W/") else tag


def _etag_matches(header_value: str | None, current: str) -> bool:
    if not header_value:
        return False
    candidates = {t.strip() for t in header_value.split(",")}
    return "*" in candidates or _strip_weak(current) in {
        _strip_weak(t) for t in candidates
    }


def _require_if_match(request: HttpRequest, c, restriction=None) -> None:
    if_match = request.headers.get("If-Match")
    if not if_match:
        raise HttpError(
            428,
            "If-Match header is required. Send the ETag from your most "
            "recent GET of this collection.",
        )
    if not _etag_matches(if_match, _collection_etag(c, restriction)):
        raise HttpError(
            412,
            "ETag mismatch: the collection has changed since you last read it. "
            "Re-fetch and retry.",
        )


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------


def _serialize_restriction(restriction) -> dict | None:
    if restriction is None:
        return None
    groups: list[dict] = []
    if restriction.restriction_type == "groups":
        groups = [{"id": g.pk, "name": g.name} for g in restriction.groups.all()]
    return {
        "type": restriction.restriction_type,
        "password": (
            restriction.password if restriction.restriction_type == "password" else None
        ),
        "groups": groups,
    }


def _serialize(c, parent_id: int | None, restriction=None) -> dict:
    return {
        "id": c.pk,
        "name": c.name,
        "depth": c.depth,
        "parent_id": parent_id,
        "view_restriction": _serialize_restriction(restriction),
    }


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------


def _resolve_collection(collection_id: int):
    from wagtail.models import Collection

    try:
        return Collection.objects.get(pk=collection_id)
    except Collection.DoesNotExist:
        raise HttpError(404, f"Collection {collection_id} not found.")


def _resolve_parent(parent_id: int | None):
    from wagtail.models import Collection

    if parent_id is None:
        return Collection.get_first_root_node()
    return _resolve_collection(parent_id)


def _member_count(collection) -> int:
    from wagtail.documents import get_document_model
    from wagtail.images import get_image_model
    from wagtailmedia.models import get_media_model

    Image = get_image_model()
    Document = get_document_model()
    Media = get_media_model()
    return (
        Image.objects.filter(collection=collection).count()
        + Document.objects.filter(collection=collection).count()
        + Media.objects.filter(collection=collection).count()
    )


def _apply_restriction(c, vr_data: ViewRestrictionWrite | None) -> None:
    """Create / update / delete the direct view restriction for this collection."""
    from wagtail.models import CollectionViewRestriction

    if vr_data is None:
        return

    if vr_data.type == "none":
        CollectionViewRestriction.objects.filter(collection=c).delete()
        return

    if vr_data.type not in ("password", "login", "groups"):
        raise HttpError(400, f"Unknown restriction type '{vr_data.type}'.")

    restriction, _ = CollectionViewRestriction.objects.get_or_create(collection=c)
    restriction.restriction_type = vr_data.type
    restriction.password = vr_data.password or ""
    restriction.save()

    if vr_data.type == "groups":
        restriction.groups.set(Group.objects.filter(pk__in=vr_data.groups))
    else:
        restriction.groups.clear()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/", response={200: CollectionList}, summary="List all collections")
def list_collections(request: HttpRequest):
    from wagtail.models import Collection, CollectionViewRestriction

    qs = list(Collection.objects.all().order_by("path"))
    if not qs:
        return {"items": [], "total": 0}

    step = qs[0].steplen  # treebeard path step length (default 4)
    path_to_id = {c.path: c.pk for c in qs}

    restrictions = {
        r.collection_id: r
        for r in CollectionViewRestriction.objects.filter(
            collection_id__in=[c.pk for c in qs]
        ).prefetch_related("groups")
    }

    items = []
    for c in qs:
        parent_path = c.path[:-step]
        parent_id = path_to_id.get(parent_path)
        items.append(_serialize(c, parent_id, restrictions.get(c.pk)))

    return {"items": items, "total": len(items)}


@router.post(
    "/",
    response={201: CollectionItem, 400: Error, 403: Error, 409: Error},
    summary="Create a collection",
)
def create_collection(
    request: HttpRequest, response: HttpResponse, payload: CollectionCreate
):
    if not request.auth.has_perm("wagtailcore.add_collection"):
        raise HttpError(403, "User does not have permission to create collections.")

    parent = _resolve_parent(payload.parent_id)

    if parent.get_children().filter(name=payload.name).exists():
        raise HttpError(
            409,
            f"A collection named '{payload.name}' already exists under this parent.",
        )

    with transaction.atomic():
        c = parent.add_child(name=payload.name)
        _apply_restriction(c, payload.view_restriction)

    restriction = None
    if payload.view_restriction and payload.view_restriction.type != "none":
        from wagtail.models import CollectionViewRestriction

        restriction = (
            CollectionViewRestriction.objects.filter(collection=c)
            .prefetch_related("groups")
            .first()
        )

    response["ETag"] = _collection_etag(c, restriction)
    return 201, _serialize(c, parent.pk, restriction)


@router.get(
    "/{collection_id}/",
    response={200: CollectionItem, 404: Error},
    summary="Get a collection",
)
def get_collection(request: HttpRequest, response: HttpResponse, collection_id: int):
    from wagtail.models import CollectionViewRestriction

    c = _resolve_collection(collection_id)
    step = c.steplen
    parent_path = c.path[:-step]
    from wagtail.models import Collection

    parent = Collection.objects.filter(path=parent_path).first()
    parent_id = parent.pk if parent else None

    restriction = (
        CollectionViewRestriction.objects.filter(collection=c)
        .prefetch_related("groups")
        .first()
    )
    response["ETag"] = _collection_etag(c, restriction)
    return _serialize(c, parent_id, restriction)


@router.patch(
    "/{collection_id}/",
    response={
        200: CollectionItem,
        400: Error,
        403: Error,
        404: Error,
        409: Error,
        412: Error,
        428: Error,
    },
    summary="Rename and/or reparent a collection",
)
def patch_collection(
    request: HttpRequest,
    response: HttpResponse,
    collection_id: int,
    payload: CollectionPatch,
):
    if not request.auth.has_perm("wagtailcore.change_collection"):
        raise HttpError(403, "User does not have permission to change collections.")

    from wagtail.models import Collection, CollectionViewRestriction

    c = _resolve_collection(collection_id)

    restriction = (
        CollectionViewRestriction.objects.filter(collection=c)
        .prefetch_related("groups")
        .first()
    )
    _require_if_match(request, c, restriction)

    if c.depth == 1:
        raise HttpError(400, "The root collection cannot be modified.")

    data = payload.model_dump(exclude_unset=True)

    with transaction.atomic():
        if "name" in data and data["name"] is not None:
            current_parent = c.get_parent()
            if (
                current_parent
                and current_parent.get_children()
                .filter(name=data["name"])
                .exclude(pk=c.pk)
                .exists()
            ):
                raise HttpError(
                    409,
                    f"A collection named '{data['name']}' already exists "
                    "under this parent.",
                )
            c.name = data["name"]
            c.save(update_fields=["name"])

        if "parent_id" in data:
            new_parent = _resolve_parent(data["parent_id"])
            if new_parent.path.startswith(c.path):
                raise HttpError(
                    400,
                    "Cannot move a collection into one of its own descendants.",
                )
            current_parent = c.get_parent()
            if current_parent is None or new_parent.pk != current_parent.pk:
                c.move(new_parent, pos="sorted-child")

        c.refresh_from_db()

        if "view_restriction" in data:
            _apply_restriction(c, payload.view_restriction)

    restriction = (
        CollectionViewRestriction.objects.filter(collection=c)
        .prefetch_related("groups")
        .first()
    )

    step = c.steplen
    parent_path = c.path[:-step]
    parent = Collection.objects.filter(path=parent_path).first()
    parent_id = parent.pk if parent else None

    response["ETag"] = _collection_etag(c, restriction)
    return _serialize(c, parent_id, restriction)


@router.delete(
    "/{collection_id}/",
    response={
        204: None,
        400: Error,
        403: Error,
        404: Error,
        409: Error,
        412: Error,
        428: Error,
    },
    summary="Delete a collection (refused if non-empty)",
)
def delete_collection(request: HttpRequest, collection_id: int):
    if not request.auth.has_perm("wagtailcore.delete_collection"):
        raise HttpError(403, "User does not have permission to delete collections.")

    from wagtail.models import CollectionViewRestriction

    c = _resolve_collection(collection_id)

    if c.depth == 1:
        raise HttpError(400, "The root collection cannot be deleted.")

    restriction = CollectionViewRestriction.objects.filter(collection=c).first()
    _require_if_match(request, c, restriction)

    child_count = c.get_children().count()
    member_count = _member_count(c)
    if child_count or member_count:
        parts: list[str] = []
        if child_count:
            parts.append(f"{child_count} child collection(s)")
        if member_count:
            parts.append(f"{member_count} media item(s)")
        raise HttpError(
            409,
            f"Collection is not empty: contains {' and '.join(parts)}. "
            "Reassign or delete its contents first.",
        )

    c.delete()
    return 204, None
