"""The studio CLI decides from whole lists, never from their first page.

``dump`` archives what is missing from a list and ``load`` maps identifiers
to ids from one, so both read every page — and end the command, rather than
decide, when the list moved while it was read.
"""

from __future__ import annotations

import pytest
import typer
from rich.progress import Progress

from phoxtail.cli.studio import client
from phoxtail.cli.studio.dump import _dump_collections

COLLECTIONS = [{"id": index, "identifier": f"collection_{index}", "name": f"Collection {index}"} for index in range(5)]


def _paged(rows, page_size=2):
    """A fake GET that answers *rows* two at a time, whatever limit is asked."""
    asked = []

    def get_json(path, **params):
        asked.append(params["offset"])
        start = params["offset"]
        return {"items": rows[start : start + page_size], "total": len(rows)}

    return get_json, asked


def test_dump_keeps_what_lies_past_the_first_page(tmp_path, monkeypatch):
    collections_dir = tmp_path / "collections"
    collections_dir.mkdir()
    for row in COLLECTIONS:
        (collections_dir / f"{row['identifier']}.md").write_text("---\nname: x\n---\n", encoding="utf-8")
    (collections_dir / "gone.md").write_text("---\nname: Gone\n---\n", encoding="utf-8")
    get_json, asked = _paged(COLLECTIONS)
    monkeypatch.setattr(client, "get_json", get_json)
    monkeypatch.setattr(client, "get_collection_by_id", lambda pk: ({**COLLECTIONS[pk], "description": ""}, None))

    with Progress() as progress:
        counts = _dump_collections(tmp_path, progress=progress)

    assert asked == [0, 2, 4]
    assert counts.written == 5
    assert counts.archived == 1
    assert sorted(path.name for path in (tmp_path / ".archive" / "collections").iterdir()) == ["gone.md"]


def test_a_list_that_moved_while_read_ends_the_command_asking_to_run_again(monkeypatch, capsys):
    pages = iter([{"items": COLLECTIONS[:2], "total": 5}, {"items": COLLECTIONS[2:4], "total": 6}])
    monkeypatch.setattr(client, "get_json", lambda path, **params: next(pages))

    with pytest.raises(typer.Exit):
        client.every_collection()

    assert "Run this again" in capsys.readouterr().out


def test_an_older_project_ends_the_command_asking_for_an_upgrade(monkeypatch, capsys):
    monkeypatch.setattr(client, "get_json", lambda path, **params: {"collections": [], "total": 0})

    with pytest.raises(typer.Exit):
        client.every_collection()

    output = capsys.readouterr().out
    assert "before lists were paged" in output
    assert "Upgrade" in output
