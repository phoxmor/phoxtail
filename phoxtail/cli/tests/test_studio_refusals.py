"""The studio CLI reports a refused request instead of mistaking it for success.

The API refuses a request for its content in two ways — 400 from a model's
own validation, 422 from the schema — and a run over many files must treat
both as a warning about that one file, never as the end of the run.
"""

from __future__ import annotations

import pytest

from phoxtail.cli.studio import client
from phoxtail.cli.studio.load import _load_collections


def _collection_file(root, stem, frontmatter):
    directory = root / "collections"
    directory.mkdir(exist_ok=True)
    (directory / f"{stem}.md").write_text(f"---\n{frontmatter}---\n", encoding="utf-8")


@pytest.mark.parametrize(
    "status, body",
    [
        (400, {"detail": "description: This field cannot be blank."}),
        (
            422,
            {"detail": [{"loc": ["body", "payload", "description"], "msg": "String should have at least 1 character"}]},
        ),
    ],
)
def test_a_refused_collection_is_a_warning_and_the_run_goes_on(tmp_path, monkeypatch, status, body):
    _collection_file(tmp_path, "refused", "name: Refused\n")
    _collection_file(tmp_path, "accepted", "name: Accepted\ndescription: Kept.\n")
    answers = {"refused": (body, status), "accepted": ({"id": 1}, 201)}
    monkeypatch.setattr(client, "create_collection", lambda identifier, **_: answers[identifier])

    counts = _load_collections(tmp_path)

    assert counts.created == 1
    assert counts.skipped_other == 1
    assert counts.warnings == [f"refused: {client.describe(body)}"]
    assert "description" in counts.warnings[0]


def test_a_schema_refusal_reads_as_field_and_reason():
    body = {"detail": [{"loc": ["body", "payload", "name"], "msg": "String should have at least 1 character"}]}

    assert client.describe(body) == "name: String should have at least 1 character"


def test_a_model_refusal_reads_as_its_detail():
    assert client.describe({"detail": "slug: already taken"}) == "slug: already taken"


@pytest.mark.parametrize("status", [400, 422])
def test_the_client_hands_a_refusal_back_instead_of_ending_the_run(httpx_mock, status):
    body = {"detail": "refused"}
    httpx_mock.add_response(status_code=status, json=body)

    assert client.create_collection(identifier="one", name="One", description="d") == (body, status)


@pytest.mark.parametrize("status", [400, 422])
def test_a_refused_session_commit_says_so_and_keeps_the_session(monkeypatch, status):
    from typer.testing import CliRunner

    from phoxtail.cli.studio import sessions

    session_data = {"variant": {"id": 7}, "etag": 'W/"x"', "html": "", "css": "", "javascript": ""}
    discarded = []
    monkeypatch.setattr(sessions, "resolve_session_id", lambda ref: "s1")
    monkeypatch.setattr(sessions.session, "read_session", lambda session_id: session_data)
    monkeypatch.setattr(sessions.session, "discard_session", discarded.append)
    body = (
        {"detail": [{"loc": ["body", "payload", "html"], "msg": "refused"}]} if status == 422 else {"detail": "refused"}
    )
    monkeypatch.setattr(client, "update_variant_by_id", lambda *args, **kwargs: (body, status, None))

    result = CliRunner().invoke(sessions.app, ["commit", "--clean"])

    assert result.exit_code == 1
    assert "server rejected the commit" in result.output
    assert discarded == []
