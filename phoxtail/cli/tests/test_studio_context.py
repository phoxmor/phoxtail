"""Tests for ``phoxtail studio context`` CLI command."""

from __future__ import annotations

import json

from pytest_httpx import HTTPXMock
from typer.testing import CliRunner

from phoxtail.cli.studio import app

runner = CliRunner()

CONTEXT_RESPONSE = {
    "block": {
        "identifier": "header_section",
        "name": "Header Section",
        "description": "A page header.",
        "field_schema": '{"fields": []}',
    },
    "collection": {
        "identifier": "general-unsorted",
        "name": "General (Unsorted)",
        "description": "Minimal design system.",
        "design_guidelines": "## Core Principles\n\nStructure dictates form.",
    },
    "design_tokens": {
        "palette_roles": [],
        "font_roles": [],
    },
    "references": [],
}


class TestContextCommand:
    def test_basic_renders_output(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(json=CONTEXT_RESPONSE)
        result = runner.invoke(app, ["context", "--block", "1", "--collection", "2", "--raw"])
        assert result.exit_code == 0
        assert "Header Section" in result.output

    def test_block_and_collection_ids_sent_to_api(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(json=CONTEXT_RESPONSE)
        runner.invoke(app, ["context", "--block", "3", "--collection", "7", "--raw"])
        req = httpx_mock.get_request()
        body = json.loads(req.content)
        assert body["block_id"] == 3
        assert body["collection_id"] == 7

    def test_references_sends_integer_ids(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(json=CONTEXT_RESPONSE)
        result = runner.invoke(
            app,
            [
                "context",
                "--block",
                "1",
                "--collection",
                "2",
                "--references",
                "5,7",
                "--raw",
            ],
        )
        assert result.exit_code == 0
        req = httpx_mock.get_request()
        body = json.loads(req.content)
        assert body["references"] == [5, 7]

    def test_references_single_id(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(json=CONTEXT_RESPONSE)
        result = runner.invoke(
            app,
            [
                "context",
                "--block",
                "1",
                "--collection",
                "2",
                "--references",
                "42",
                "--raw",
            ],
        )
        assert result.exit_code == 0
        req = httpx_mock.get_request()
        body = json.loads(req.content)
        assert body["references"] == [42]

    def test_no_references_omits_key_from_body(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(json=CONTEXT_RESPONSE)
        runner.invoke(app, ["context", "--block", "1", "--collection", "2", "--raw"])
        req = httpx_mock.get_request()
        body = json.loads(req.content)
        assert "references" not in body

    def test_references_rejects_non_integer(self):
        result = runner.invoke(
            app,
            [
                "context",
                "--block",
                "1",
                "--collection",
                "2",
                "--references",
                "dark,light",
            ],
        )
        assert result.exit_code == 1
        assert "must be comma-separated variant IDs" in result.output

    def test_references_rejects_mixed_valid_invalid(self):
        result = runner.invoke(
            app,
            ["context", "--block", "1", "--collection", "2", "--references", "5,bad"],
        )
        assert result.exit_code == 1
        assert "bad" in result.output
