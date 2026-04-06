"""Tests for the Phoxtail Studio MCP server.

Verifies that:
- The MCP server exposes the correct set of tools.
- Each tool calls the correct API endpoint and returns well-formed JSON.
- Error responses (412, 409, 404) are surfaced gracefully, not raised.
- The ``phoxtail studio mcp serve`` command is wired up correctly.

All HTTP calls are intercepted by ``pytest-httpx`` so no running Django
app is required.
"""

from __future__ import annotations

import json

from pytest_httpx import HTTPXMock
from typer.testing import CliRunner

from phoxtail.cli.studio.mcp import (
    _url,
    create_variant,
    diff_variant,
    get_collection,
    get_context,
    get_variant,
    list_blocks,
    list_collections,
    list_variants,
    mcp_server,
    update_variant,
)

runner = CliRunner()

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_VARIANT_SUMMARY = {
    "identifier": "centered",
    "name": "Centered",
    "description": "A centered hero section.",
    "is_default": True,
    "block": {"identifier": "header_section", "name": "Header Section"},
    "collection": {"identifier": "ground-state", "name": "Ground State"},
}

SAMPLE_VARIANT_DETAIL = {
    **SAMPLE_VARIANT_SUMMARY,
    "html": "<div>hello</div>",
    "css": ".hero { color: red; }",
    "javascript": "console.log('hi');",
}


# ---------------------------------------------------------------------------
# Tool registration
# ---------------------------------------------------------------------------


class TestMCPToolRegistration:
    """The MCP server advertises exactly the tools specified in the roadmap."""

    def test_server_name(self):
        assert mcp_server.name == "phoxtail-studio"

    def test_expected_tools_registered(self):
        expected = {
            "phoxtail_list_variants",
            "phoxtail_list_collections",
            "phoxtail_list_blocks",
            "phoxtail_get_collection",
            "phoxtail_get_variant",
            "phoxtail_get_context",
            "phoxtail_diff_variant",
            "phoxtail_update_variant",
            "phoxtail_create_variant",
        }
        registered = set(mcp_server._tool_manager._tools.keys())
        assert expected == registered


# ---------------------------------------------------------------------------
# Listing tools
# ---------------------------------------------------------------------------


class TestListVariants:
    def test_returns_json(self, httpx_mock: HTTPXMock):
        payload = {"variants": [SAMPLE_VARIANT_SUMMARY], "total": 1}
        httpx_mock.add_response(url=_url("/variants/"), json=payload)
        result = json.loads(list_variants())
        assert result["total"] == 1
        assert result["variants"][0]["identifier"] == "centered"

    def test_passes_filters(self, httpx_mock: HTTPXMock):
        payload = {"variants": [], "total": 0}
        httpx_mock.add_response(json=payload)
        list_variants(block="hero", collection="ground-state")
        req = httpx_mock.get_request()
        assert "block=hero" in str(req.url)
        assert "collection=ground-state" in str(req.url)


class TestListCollections:
    def test_returns_json(self, httpx_mock: HTTPXMock):
        payload = {"collections": [], "total": 0}
        httpx_mock.add_response(url=_url("/collections/"), json=payload)
        result = json.loads(list_collections())
        assert result["total"] == 0


class TestListBlocks:
    def test_returns_json(self, httpx_mock: HTTPXMock):
        payload = {"blocks": [], "total": 0}
        httpx_mock.add_response(url=_url("/blocks/"), json=payload)
        result = json.loads(list_blocks())
        assert result["total"] == 0


# ---------------------------------------------------------------------------
# Read tools
# ---------------------------------------------------------------------------


class TestGetCollection:
    def test_returns_rendered_design_tokens(self, httpx_mock: HTTPXMock):
        payload = {
            "identifier": "ground-state",
            "name": "Ground State",
            "description": "Minimal design system.",
            "design_tokens": "Primary: blue\nSurface: white",
        }
        httpx_mock.add_response(
            url=_url("/collections/ground-state/render/"), json=payload
        )
        result = json.loads(get_collection("ground-state"))
        assert result["identifier"] == "ground-state"
        assert result["design_tokens"] == "Primary: blue\nSurface: white"
        assert "template" not in result


class TestGetVariant:
    def test_includes_etag(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            json=SAMPLE_VARIANT_DETAIL,
            headers={"ETag": 'W/"abc123"'},
        )
        result = json.loads(get_variant("centered", block="header_section"))
        assert result["html"] == "<div>hello</div>"
        assert result["_etag"] == 'W/"abc123"'

    def test_passes_disambiguators(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            json=SAMPLE_VARIANT_DETAIL,
            headers={"ETag": 'W/"abc123"'},
        )
        get_variant("centered", block="hero", collection="ground-state")
        req = httpx_mock.get_request()
        assert "block=hero" in str(req.url)


class TestGetContext:
    """The ``phoxtail_get_context`` tool renders the context template."""

    CONTEXT_RESPONSE = {
        "block": {
            "identifier": "header_section",
            "name": "Header Section",
            "description": "A page header with title and subtitle.",
            "field_schema": '{"fields": []}',
        },
        "variant": {
            "identifier": "centered",
            "name": "Centered",
            "description": "A centered hero section.",
            "html": "<div>hello</div>",
            "css": ".hero { color: red; }",
            "javascript": "",
        },
        "collection": {
            "identifier": "ground-state",
            "name": "Ground State",
            "description": "Minimal design system.",
            "design_tokens": "Primary: blue",
        },
        "references": [],
    }

    def test_renders_context_template(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(json=self.CONTEXT_RESPONSE)
        result = get_context(block="header_section", variant="centered")
        assert "Header Section" in result
        assert "DTL Reference" in result
        assert "CSS Scoping" in result
        assert "<div>hello</div>" in result
        assert "Primary: blue" in result

    def test_sends_references(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(json=self.CONTEXT_RESPONSE)
        get_context(
            block="header_section",
            variant="centered",
            references=["dark", "light"],
        )
        req = httpx_mock.get_request()
        body = json.loads(req.content)
        assert body["references"] == ["dark", "light"]


# ---------------------------------------------------------------------------
# Diff tool
# ---------------------------------------------------------------------------


class TestDiffVariant:
    def test_shows_diff(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            json=SAMPLE_VARIANT_DETAIL,
            headers={"ETag": 'W/"abc123"'},
        )
        result = diff_variant(
            "centered", block="header_section", html="<div>goodbye</div>"
        )
        assert "--- a/html" in result
        assert "+++ b/html" in result
        assert "-<div>hello</div>" in result
        assert "+<div>goodbye</div>" in result

    def test_no_diff_when_unchanged(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            json=SAMPLE_VARIANT_DETAIL,
            headers={"ETag": 'W/"abc123"'},
        )
        result = diff_variant(
            "centered", block="header_section", html="<div>hello</div>"
        )
        assert result == "(no differences)"

    def test_omitted_fields_not_diffed(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            json=SAMPLE_VARIANT_DETAIL,
            headers={"ETag": 'W/"abc123"'},
        )
        result = diff_variant(
            "centered", block="header_section", css=".hero { color: blue; }"
        )
        assert "a/css" in result
        assert "a/html" not in result


# ---------------------------------------------------------------------------
# Write tools
# ---------------------------------------------------------------------------


class TestUpdateVariant:
    def test_success_returns_updated_data(self, httpx_mock: HTTPXMock):
        updated = {**SAMPLE_VARIANT_DETAIL, "html": "<div>new</div>"}
        httpx_mock.add_response(
            json=updated,
            headers={"ETag": 'W/"new456"'},
        )
        result = json.loads(
            update_variant(
                "centered",
                block="header_section",
                etag='W/"abc123"',
                html="<div>new</div>",
            )
        )
        assert result["html"] == "<div>new</div>"
        assert result["_etag"] == 'W/"new456"'

    def test_sends_if_match_header(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(json=SAMPLE_VARIANT_DETAIL, headers={"ETag": 'W/"x"'})
        update_variant("centered", block="header_section", etag='W/"abc123"', html="x")
        req = httpx_mock.get_request()
        assert req.headers["If-Match"] == 'W/"abc123"'

    def test_conflict_returns_error_json(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            status_code=412,
            json={"detail": "ETag mismatch"},
        )
        result = json.loads(
            update_variant(
                "centered",
                block="header_section",
                etag='W/"stale"',
                html="x",
            )
        )
        assert result["error"] == "conflict"

    def test_precondition_required(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            status_code=428,
            json={"detail": "If-Match required"},
        )
        result = json.loads(
            update_variant("centered", block="header_section", etag="", html="x")
        )
        assert result["error"] == "precondition_required"


class TestCreateVariant:
    def test_success(self, httpx_mock: HTTPXMock):
        created = {
            **SAMPLE_VARIANT_DETAIL,
            "identifier": "new-variant",
            "name": "New Variant",
        }
        httpx_mock.add_response(
            status_code=201,
            json=created,
            headers={"ETag": 'W/"fresh"'},
        )
        result = json.loads(
            create_variant(
                identifier="new-variant",
                name="New Variant",
                block="header_section",
                collection="ground-state",
                html="<div>new</div>",
            )
        )
        assert result["identifier"] == "new-variant"
        assert result["_etag"] == 'W/"fresh"'

    def test_conflict_existing(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            status_code=409,
            json={"detail": "Variant already exists."},
        )
        result = json.loads(
            create_variant(
                identifier="centered",
                name="Centered",
                block="header_section",
                collection="ground-state",
            )
        )
        assert result["error"] == "conflict"

    def test_block_not_found(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            status_code=404,
            json={"detail": "Block 'nonexistent' not found."},
        )
        result = json.loads(
            create_variant(
                identifier="x",
                name="X",
                block="nonexistent",
                collection="ground-state",
            )
        )
        assert result["error"] == "not_found"


# ---------------------------------------------------------------------------
# CLI wiring
# ---------------------------------------------------------------------------


class TestServeCommand:
    """The ``phoxtail studio mcp serve`` command is registered and reachable."""

    def test_help_text(self):
        from phoxtail.cli.studio import app as studio_app

        result = runner.invoke(studio_app, ["mcp", "serve", "--help"])
        assert result.exit_code == 0
        assert "MCP" in result.output or "stdio" in result.output
