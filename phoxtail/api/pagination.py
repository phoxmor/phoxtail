"""Every list the API serves comes back one page at a time, in one shape.

An endpoint on :class:`Router` that declares a list response —
``response=list[X]`` or ``response={200: list[X], ...}`` — and returns a
queryset, or a list it built in memory, is paginated without saying so::

    GET /api/users/v1/genders/?limit=50&offset=100
    {"items": [...], "total": 123}

``total`` counts every match, not the page, so a caller can tell whether
to narrow its question or read on. Apps never write ``limit``, ``offset``
or ``total`` themselves; :func:`unpaginated` is the check that they didn't.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from django.db.models import QuerySet
from ninja import Field, Schema
from ninja import Router as NinjaRouter
from ninja.constants import NOT_SET
from ninja.pagination import PaginationBase, paginate
from ninja.signature.details import is_collection_type

DEFAULT_LIMIT = 50
MAX_LIMIT = 500


class Pagination(PaginationBase):
    """Limit/offset over a queryset in a stable order, or over a list as built.

    A request for more than :data:`MAX_LIMIT` rows is refused with 422
    rather than silently cut short, so a caller never mistakes a capped
    page for the whole answer.
    """

    class Input(Schema):
        limit: int = Field(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT, description="Rows to return.")
        offset: int = Field(0, ge=0, description="Rows to skip.")

    class Output(Schema):
        items: list[Any]
        total: int = Field(description="Rows matching the request, across every page.")

    def paginate_queryset(self, queryset: Any, pagination: Input, request: Any, **params: Any) -> dict:
        start, stop = pagination.offset, pagination.offset + pagination.limit
        if isinstance(queryset, QuerySet):
            queryset = in_stable_order(queryset)
            return {"items": queryset[start:stop], "total": queryset.count()}
        # A list built in memory keeps the order it was built in. A tuple is
        # not accepted: a view returning ``(404, body)`` must stay an error.
        if isinstance(queryset, list):
            return {"items": queryset[start:stop], "total": len(queryset)}
        raise TypeError(
            f"A paginated endpoint must return a QuerySet or a list, not {type(queryset).__name__}. "
            "Narrow a search with phoxtail.api.search.narrow_by_search() instead of returning its results."
        )


def in_stable_order(queryset: QuerySet) -> QuerySet:
    """*queryset* in its own order, with the primary key breaking ties.

    Offset pages are only disjoint if every row has one position. An
    ordering by ``name`` alone lets two rows of the same name swap
    between requests, so one is served twice and the other never.
    """
    query = queryset.query
    ordering = list(query.order_by)
    if not ordering and query.default_ordering:
        ordering = list(query.get_meta().ordering)
    return queryset.order_by(*ordering, "pk")


def _lists(response: Any) -> bool:
    # ninja's own RouterPaginated recognises only a bare list, and every
    # guarded endpoint also declares its refusals: {200: list[X], 403: ...}.
    if isinstance(response, dict):
        response = response.get(200)
    return response is not None and response is not NOT_SET and is_collection_type(response)


class Router(NinjaRouter):
    """The router every phoxtail app's API is built from.

    Identical to ninja's, except that a GET declaring a list response is
    paginated by :class:`Pagination`. A write that answers with a list —
    the categories it just set — returns it whole: the caller asked for
    that change, not for a page of its result.
    """

    def add_api_operation(self, path: str, methods: list[str], view_func: Any, **kwargs: Any) -> None:
        if methods == ["GET"] and _lists(kwargs.get("response")):
            view_func = paginate(Pagination)(view_func)
        return super().add_api_operation(path, methods, view_func, **kwargs)


def _operations(router: NinjaRouter) -> Iterator[tuple[str, Any]]:
    for mount in router.build_routers(""):
        for path, view in mount.template.path_operations.items():
            for operation in view.operations:
                yield mount.prefix + path, operation


def _envelope(model: Any) -> bool:
    """Whether *model* is a list wrapped by hand: one list field and a count."""
    fields = getattr(model, "model_fields", None) or {}
    listed = [name for name, field in fields.items() if is_collection_type(field.annotation)]
    return len(fields) == 2 and len(listed) == 1 and "total" in fields


def unpaginated(router: NinjaRouter) -> list[str]:
    """Every operation under *router* that serves a list without paginating it.

    Catches both ways of getting it wrong on a GET: a list response on
    ninja's plain ``Router``, and an envelope assembled by hand. Writes are
    not asked. An app's test suite calls it on its own router and asserts
    the answer is empty.
    """
    found = []
    for path, operation in _operations(router):
        if operation.methods != ["GET"] or getattr(operation.view_func, "_ninja_is_paginated", False):
            continue
        model = operation.response_models.get(200)
        if model is None or model is NOT_SET:
            continue
        response = model.__annotations__["response"]
        if is_collection_type(response) or _envelope(response):
            found.append(f"{'/'.join(operation.methods)} {path}")
    return found
