"""Reading a whole paged list: all of it, or a refusal when it is seen to move.

What offset paging can see: ``total`` changing, a row read twice, the list
running out early. What it cannot — one row removed behind the read position
while another is added ahead of it — is stated in the module, not tested.
"""

from __future__ import annotations

import pytest

from phoxtail.core.paging import MAX_LIMIT, ListChanged, NotAPagedList, every_item


def _server(rows, *, page_size=MAX_LIMIT):
    """A fake list endpoint over *rows*, recording what each call asked."""
    asked = []

    def fetch(params):
        asked.append(params)
        start = params["offset"]
        return {"items": rows[start : start + min(params["limit"], page_size)], "total": len(rows)}

    return fetch, asked


def _rows(count):
    return [{"id": index, "name": f"Row {index}"} for index in range(count)]


def test_a_list_on_one_page_is_read_in_one_call():
    fetch, asked = _server(_rows(3))

    assert [row["id"] for row in every_item(fetch)] == [0, 1, 2]
    assert asked == [{"limit": MAX_LIMIT, "offset": 0}]


def test_a_list_over_many_pages_is_read_to_the_end():
    fetch, asked = _server(_rows(7), page_size=3)

    assert [row["id"] for row in every_item(fetch)] == list(range(7))
    assert [call["offset"] for call in asked] == [0, 3, 6]


def test_filters_go_with_every_page():
    fetch, asked = _server(_rows(4), page_size=2)

    every_item(fetch, block="hero", search=None)

    assert all(call["block"] == "hero" and "search" in call for call in asked)


def test_an_empty_list_is_one_call():
    fetch, asked = _server([])

    assert every_item(fetch) == []
    assert len(asked) == 1


def test_a_list_that_grows_while_read_is_refused():
    rows = _rows(4)
    fetch, _ = _server(rows, page_size=2)

    def growing(params):
        page = fetch(params)
        rows.append({"id": 100 + len(rows)})
        return page

    with pytest.raises(ListChanged, match="4 items when reading began"):
        every_item(growing)


def test_a_list_that_shrinks_before_the_end_is_refused():
    pages = iter([{"items": _rows(2), "total": 4}, {"items": [], "total": 4}])

    with pytest.raises(ListChanged, match="Read 2 of 4"):
        every_item(lambda params: next(pages))


def test_a_row_read_twice_is_refused():
    # An insert near the front shifts the second page back by one.
    pages = iter([{"items": _rows(2), "total": 4}, {"items": _rows(3)[1:], "total": 4}])

    with pytest.raises(ListChanged, match="Item 1 was read twice"):
        every_item(lambda params: next(pages))


def test_a_row_keyed_by_uuid_read_twice_is_refused():
    # Most apps never expose a database id; their rows are keyed by uuid.
    rows = [{"uuid": f"u{index}"} for index in range(3)]
    pages = iter([{"items": rows[:2], "total": 4}, {"items": rows[1:3], "total": 4}])

    with pytest.raises(ListChanged, match="Item u1 was read twice"):
        every_item(lambda params: next(pages))


def test_nothing_is_handed_over_until_the_whole_list_is_read():
    pages = iter([{"items": _rows(2), "total": 3}, {"items": [], "total": 3}])
    received = []

    with pytest.raises(ListChanged):
        received.extend(every_item(lambda params: next(pages)))

    assert received == []


def test_an_answer_that_is_not_a_paged_list_is_refused_by_name():
    # A server from before lists were paged answers everything at once.
    with pytest.raises(NotAPagedList, match="before lists were paged"):
        every_item(lambda params: {"variants": [], "total": 0})


def test_a_failure_to_fetch_is_not_swallowed():
    def failing(params):
        raise ConnectionError("unreachable")

    with pytest.raises(ConnectionError):
        every_item(failing)


def test_reading_a_list_needs_no_django():
    # The CLI reads lists before any project is set up; a fresh interpreter,
    # because this test process has long since imported everything.
    import subprocess
    import sys

    code = "import sys, phoxtail.core.paging; print(sorted(m for m in ('django', 'ninja') if m in sys.modules))"
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)

    assert out.stdout.strip() == "[]"
