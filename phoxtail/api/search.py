"""Search that narrows a list instead of replacing it."""

from __future__ import annotations

from django.db.models import QuerySet


def narrow_by_search(queryset: QuerySet, query: str) -> QuerySet:
    """Restrict *queryset* to the rows Wagtail autocomplete matches.

    ``autocomplete()`` returns ``SearchResults``, which drops the
    queryset's ordering, ``select_related`` and annotations, and cannot be
    paginated as a queryset. Feeding the matched pks back through the
    original queryset keeps all of them, at the cost of one extra query.
    Matches come back in the list's own order, not ranked by relevance.
    """
    from wagtail.search.backends import get_search_backend

    matched = get_search_backend().autocomplete(query, queryset)
    return queryset.filter(pk__in=[obj.pk for obj in matched])
