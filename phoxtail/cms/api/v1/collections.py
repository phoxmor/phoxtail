"""``/api/cms/v1/collections/`` — Wagtail Collection CRUD.

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

from phoxtail.api.auth import scoped
from phoxtail.cms.api.v1._permissions import manageable, may_move, require_action

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
    return "*" in candidates or _strip_weak(current) in {_strip_weak(t) for t in candidates}


def _require_if_match(request: HttpRequest, c, restriction=None) -> None:
    if_match = request.headers.get("If-Match")
    if not if_match:
        raise HttpError(
            428,
            "If-Match header is required. Send the ETag from your most recent GET of this collection.",
        )
    if not _etag_matches(if_match, _collection_etag(c, restriction)):
        raise HttpError(
            412,
            "ETag mismatch: the collection has changed since you last read it. Re-fetch and retry.",
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
        "password": (restriction.password if restriction.restriction_type == "password" else None),
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


def _resolve_collection(collection_id: int, within=None):
    """Fetch a collection, optionally only from a permitted queryset.

    Passing *within* makes a collection the caller may not manage answer 404
    rather than 403, which is how Wagtail's own choosers behave and what
    keeps an unprivileged caller from mapping the tree by asking.
    """
    from wagtail.models import Collection

    qs = Collection.objects.all() if within is None else within
    try:
        return qs.get(pk=collection_id)
    except Collection.DoesNotExist:
        raise HttpError(404, f"Collection {collection_id} not found.")


def _resolve_parent(parent_id: int | None):
    from wagtail.models import Collection

    if parent_id is None:
        return Collection.get_first_root_node()
    return _resolve_collection(parent_id)


def _collection_contents(collection) -> list[dict]:
    """What is inside this collection, asked the way Wagtail asks it.

    Wagtail's own delete view calls the ``describe_collection_contents``
    hook and refuses if anything answers. Counting images, documents and
    media directly — which is what this used to do — misses two things:

    * **descendant collections.** ``describe_collection_children`` is one
      of the registered hooks, and it counts the whole subtree rather than
      direct children, so it is stricter than the ``get_children()`` check
      it replaces;
    * **anything any other installed app keeps in collections.** The hook
      is the extension point; a model that registers one is invisible to a
      hand-written count, and the API would then delete a collection the
      admin refuses to delete.

    The ``item_type and item_type["count"] > 0`` filter is Wagtail's too: a
    hook may answer ``None`` or a zero count, and neither means occupied.
    """
    from wagtail import hooks

    described = [hook(collection) for hook in hooks.get_hooks("describe_collection_contents")]
    return [item for item in described if item and item["count"] > 0]


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


@router.get(
    "/",
    response={200: CollectionList},
    summary="List all collections",
    # Only the credential's half is asked here. Wagtail grants collections
    # per collection, so has_perm() would refuse people it genuinely permits
    # — the person's half is answered below, against the policy.
    #
    # view_collection is a Django default row that Wagtail references
    # nowhere, so it names the act rather than gating it; the gate is the
    # narrowing. See _permissions.py.
    auth=scoped("wagtailcore.view_collection"),
)
def list_collections(request: HttpRequest):
    from wagtail.models import Collection, CollectionViewRestriction

    # Narrowed rather than refused: being shown fewer collections is a true
    # answer to "which may I manage", where a 403 would claim the act itself
    # was forbidden. The parent ids below are resolved against the *whole*
    # tree, so a visible child still reports the real parent it hangs from.
    visible = set(manageable(request.auth.user).values_list("pk", flat=True))
    qs = list(Collection.objects.all().order_by("path"))
    if not qs:
        return {"items": [], "total": 0}

    step = qs[0].steplen  # treebeard path step length (default 4)
    path_to_id = {c.path: c.pk for c in qs}

    restrictions = {
        r.collection_id: r
        for r in CollectionViewRestriction.objects.filter(collection_id__in=[c.pk for c in qs]).prefetch_related(
            "groups"
        )
    }

    items = []
    for c in qs:
        if c.pk not in visible:
            continue
        parent_path = c.path[:-step]
        parent_id = path_to_id.get(parent_path)
        items.append(_serialize(c, parent_id, restrictions.get(c.pk)))

    return {"items": items, "total": len(items)}


@router.post(
    "/",
    response={201: CollectionItem, 400: Error, 403: Error, 409: Error},
    summary="Create a collection",
    auth=scoped("wagtailcore.add_collection"),
)
def create_collection(request: HttpRequest, response: HttpResponse, payload: CollectionCreate):
    parent = _resolve_parent(payload.parent_id)
    # Wagtail's Create view offers only the collections you may add under,
    # so a parent outside that set is a refusal rather than a 404. Omitting
    # parent_id means the root, which is itself only permitted to someone
    # granted on the root.
    require_action(
        request.auth.user,
        "add",
        parent,
        detail="User cannot add collections under that parent.",
    )

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

        restriction = CollectionViewRestriction.objects.filter(collection=c).prefetch_related("groups").first()

    response["ETag"] = _collection_etag(c, restriction)
    return 201, _serialize(c, parent.pk, restriction)


@router.get(
    "/{collection_id}/",
    response={200: CollectionItem, 404: Error},
    summary="Get a collection",
    auth=scoped("wagtailcore.view_collection"),
)
def get_collection(request: HttpRequest, response: HttpResponse, collection_id: int):
    from wagtail.models import CollectionViewRestriction

    # Resolved *within* the permitted set, so a collection the caller may not
    # manage is a collection that is not there. 404 rather than 403 is what
    # stops the ids being swept to map a tree you cannot see.
    c = _resolve_collection(collection_id, within=manageable(request.auth.user))
    step = c.steplen
    parent_path = c.path[:-step]
    from wagtail.models import Collection

    parent = Collection.objects.filter(path=parent_path).first()
    parent_id = parent.pk if parent else None

    restriction = CollectionViewRestriction.objects.filter(collection=c).prefetch_related("groups").first()
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
    auth=scoped("wagtailcore.change_collection"),
)
def patch_collection(
    request: HttpRequest,
    response: HttpResponse,
    collection_id: int,
    payload: CollectionPatch,
):
    from wagtail.models import Collection, CollectionViewRestriction

    c = _resolve_collection(collection_id)
    require_action(request.auth.user, "change", c)

    restriction = CollectionViewRestriction.objects.filter(collection=c).prefetch_related("groups").first()
    _require_if_match(request, c, restriction)

    if c.depth == 1:
        raise HttpError(400, "The root collection cannot be modified.")

    data = payload.model_dump(exclude_unset=True)

    with transaction.atomic():
        if "name" in data and data["name"] is not None:
            current_parent = c.get_parent()
            if current_parent and current_parent.get_children().filter(name=data["name"]).exclude(pk=c.pk).exists():
                raise HttpError(
                    409,
                    f"A collection named '{data['name']}' already exists under this parent.",
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
                # Two further asks, both Wagtail's. Landing somewhere needs
                # the right to add there...
                require_action(
                    request.auth.user,
                    "add",
                    new_parent,
                    detail="User cannot add collections under that parent.",
                )
                # ...and a collection carrying your own grant may not be
                # moved at all: a grant flows down, so moving the node it
                # names changes what it reaches. Wagtail drops the parent
                # field from the form; we refuse the reparent.
                if not may_move(request.auth.user, c):
                    raise HttpError(
                        403,
                        "User cannot move a collection their own permissions are assigned on.",
                    )
                c.move(new_parent, pos="sorted-child")

        c.refresh_from_db()

        if "view_restriction" in data:
            _apply_restriction(c, payload.view_restriction)

    restriction = CollectionViewRestriction.objects.filter(collection=c).prefetch_related("groups").first()

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
    auth=scoped("wagtailcore.delete_collection"),
)
def delete_collection(request: HttpRequest, collection_id: int):
    from wagtail.models import CollectionViewRestriction

    c = _resolve_collection(collection_id)
    require_action(request.auth.user, "delete", c)

    if c.depth == 1:
        raise HttpError(400, "The root collection cannot be deleted.")

    restriction = CollectionViewRestriction.objects.filter(collection=c).first()
    _require_if_match(request, c, restriction)

    contents = _collection_contents(c)
    if contents:
        described = " and ".join(item["count_text"] for item in contents)
        raise HttpError(
            409,
            f"Collection is not empty: contains {described}. Reassign or delete its contents first.",
        )

    c.delete()
    return 204, None
