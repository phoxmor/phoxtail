"""How a phoxtail list is paged, on both sides of the wire.

The API answers every list one page at a time, as ``{"items": [...],
"total": N}``, chosen by ``limit`` and ``offset`` (see
:mod:`phoxtail.api.pagination`, which takes its bounds from here). Most
callers want a page. Some need the whole list — a dump that decides what is
stale by what is missing, a sync that compares every row — and
:func:`every_item` is how they read it.

Offset paging can see a list change only by its effects: ``total`` moving, a
row arriving twice, the list running out early. One edit leaves no trace — a
row removed before the read position while another is added after it keeps
``total`` and repeats nothing, and a row is skipped. A caller that acts on
what is missing should not run while the list is being edited.

No Django here: the CLI imports this before any project is set up.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

DEFAULT_LIMIT = 50

# every_item() asks for pages this size, from this project and from remote
# ones. Lowering it later makes a client that still asks for the old maximum
# fail with 422 against the new server, so treat it as part of the contract.
MAX_LIMIT = 500


class ListChanged(RuntimeError):
    """The list moved while it was being read, so what was read is not it.

    A row added, removed or reordered between two pages shifts every later
    offset: one row is read twice and another never. A caller acting on the
    whole list — archiving what is missing, mapping every identifier — must
    not act on that; one only displaying it may catch this and show a page.
    """


class NotAPagedList(ValueError):
    """The answer is not a paged list — typically a server from before lists
    were paged, which answers everything at once under the resource's name."""


def every_item(fetch: Callable[[dict[str, Any]], dict[str, Any]], **filters: Any) -> list[dict[str, Any]]:
    """Every item of a paged list, read a page at a time.

    *fetch* is called with the query parameters for one page — *filters*
    plus ``limit`` and ``offset`` — and returns that page's decoded JSON; it
    raises on an HTTP failure. Reading stops once ``total`` items have been
    read; running out sooner raises :class:`ListChanged`.

    The whole list is returned at once, never item by item, so a caller
    cannot have acted on the first pages when a later one reveals the list
    moved.
    """
    items: list[dict[str, Any]] = []
    offset = 0
    total: int | None = None
    seen: set[Any] = set()
    while True:
        page = fetch({**filters, "limit": MAX_LIMIT, "offset": offset})
        if not isinstance(page, dict) or "items" not in page or "total" not in page:
            raise NotAPagedList(
                "Expected a paged list ({'items': [...], 'total': N}); the server answered "
                f"with {sorted(page) if isinstance(page, dict) else type(page).__name__}. "
                "It may run a phoxtail from before lists were paged."
            )
        if total is None:
            total = page["total"]
        elif page["total"] != total:
            raise ListChanged(f"The list held {total} items when reading began and {page['total']} now.")

        for item in page["items"]:
            key = _identity(item)
            if key is not None:
                if key in seen:
                    raise ListChanged(f"Item {key} was read twice: the list was reordered while it was read.")
                seen.add(key)
            items.append(item)

        offset += len(page["items"])
        if offset >= total:
            return items
        if not page["items"]:
            raise ListChanged(f"Read {offset} of {total} items before the list ran out.")


def _identity(item: Any) -> Any:
    # Lists address their rows by ``id`` or, in the apps that never expose a
    # database key, by ``uuid``.
    if not isinstance(item, dict):
        return None
    return item.get("id", item.get("uuid"))
