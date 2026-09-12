"""How an MCP tool declares what its call changed.

A tool result is the only place that knows what a call touched: the
arguments differ from tool to tool (``create_page`` takes a parent,
``move_page`` a page and a target), and the response body does not carry
the tree position at all. So tools say it themselves, on their own
result, and readers pick it up without a tool-name map.

That keeps the mechanism open to every app. A tool discovered in some
app's ``mcp/`` package declares a change exactly the way a core one does,
and nothing in phoxtail needs to know the tool exists.

Two markers, for the two shapes of change:

``_changed_blocks``
    UUIDs of blocks whose content changed within one page. The page is
    known from the call's own ``page_id``.

``_changed_pages``
    Ids of pages touched by a change to the tree itself — creating,
    moving, deleting, renaming or (un)publishing a page.

The chat stream (``phoxtail.agent.api.v1.chat``) is the reader today: it
turns the markers into ``blocks_changed`` and ``pages_changed`` SSE
events, which the phoxtail bar re-broadcasts to whatever is on screen.
It is not the only reader there could be, which is why nothing here
mentions events.
"""

from __future__ import annotations

from typing import Any


def _ids(values: tuple[Any, ...], kind: type) -> list[Any]:
    """De-duplicated ids of ``kind``, in the order given.

    Anything absent is dropped — ``None``, and equally the empty string a
    response gives back for an id it could not report — so a caller can
    pass a response field straight through without checking it first.
    """
    return list(dict.fromkeys(v for v in values if v and isinstance(v, kind)))


def mark_changed_pages(result: dict[str, Any], *page_ids: Any) -> dict[str, Any]:
    """Declare a change to the page tree, and return ``result``.

    Pass every page the change concerns — for a create or a move that
    means the parent or target as well as the page itself, since a view
    listing that parent has never seen the new id and could not match on
    it.

    Readers use the ids only to decide *whether* a change concerns what
    they show, never as a surgical target: a tree change shifts the
    position of every page after it, so the view re-derives itself
    either way.

    Always a list. One tool call is one result, so a bulk tool declares
    every id it touched without needing a different shape::

        return json.dumps(mark_changed_pages(data, data.get("id"), parent))
    """
    result["_changed_pages"] = _ids(page_ids, int)
    return result


def mark_changed_blocks(result: dict[str, Any], *block_uuids: Any) -> dict[str, Any]:
    """Declare which blocks a call changed, and return ``result``.

    Block changes are addressable in a way tree changes are not: a reader
    can re-render exactly these blocks and leave the rest of the page
    alone. Pass the uuids the call touched::

        return json.dumps(mark_changed_blocks(data, block_uuid))
    """
    result["_changed_blocks"] = _ids(block_uuids, str)
    return result
