"""Tests for the Phoxtail MCP server.

Verifies that:
- The MCP server exposes the correct set of tools.
- Each tool calls the correct API endpoint and returns well-formed JSON.
- Error responses (412, 409, 404) are surfaced gracefully, not raised.
- The ``phoxtail mcp serve`` command is wired up correctly.

All HTTP calls are intercepted by ``pytest-httpx`` so no running Django
app is required.
"""

from __future__ import annotations

import json

from pytest_httpx import HTTPXMock
from typer.testing import CliRunner

from phoxtail.mcp import mcp_server
from phoxtail.mcp._http import url
from phoxtail.mcp.studio.blocks import (
    create_block,
    get_block,
    list_blocks,
    update_block,
)
from phoxtail.mcp.studio.collections import get_collection, list_collections
from phoxtail.mcp.studio.context import get_context
from phoxtail.mcp.studio.prompts import design_block
from phoxtail.mcp.studio.resources import schema_reference
from phoxtail.mcp.studio.variants import (
    create_variant,
    diff_variant,
    get_variant,
    list_variants,
    update_variant,
)

runner = CliRunner()

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_VARIANT_SUMMARY = {
    "id": 1,
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
        assert mcp_server.name == "phoxtail"

    def test_expected_tools_registered(self):
        studio_tools = {
            "phoxtail_studio_list_variants",
            "phoxtail_studio_list_collections",
            "phoxtail_studio_list_blocks",
            "phoxtail_studio_get_collection",
            "phoxtail_studio_get_variant",
            "phoxtail_studio_get_block",
            "phoxtail_studio_get_context",
            "phoxtail_studio_diff_variant",
            "phoxtail_studio_update_variant",
            "phoxtail_studio_update_block",
            "phoxtail_studio_create_variant",
            "phoxtail_studio_create_block",
            "phoxtail_studio_create_collection",
            "phoxtail_studio_update_collection",
        }
        pages_tools = {
            "phoxtail_pages_list_pages",
            "phoxtail_pages_get_page",
            "phoxtail_pages_update_page",
            "phoxtail_pages_publish",
            "phoxtail_pages_unpublish",
            "phoxtail_pages_get_body",
            "phoxtail_pages_replace_body",
            "phoxtail_pages_list_images",
            "phoxtail_pages_list_documents",
            "phoxtail_images_upload",
            "phoxtail_images_get",
            "phoxtail_images_view",
            "phoxtail_images_update",
            "phoxtail_documents_get",
            "phoxtail_documents_upload",
            "phoxtail_documents_update",
            "phoxtail_videos_list",
            "phoxtail_videos_get",
            "phoxtail_videos_upload",
            "phoxtail_videos_update",
            "phoxtail_audio_list",
            "phoxtail_audio_get",
            "phoxtail_audio_upload",
            "phoxtail_audio_update",
        }
        expected = studio_tools | pages_tools
        registered = set(mcp_server._tool_manager._tools.keys())
        assert expected == registered


# ---------------------------------------------------------------------------
# Listing tools
# ---------------------------------------------------------------------------


class TestListVariants:
    def test_returns_json(self, httpx_mock: HTTPXMock):
        payload = {"variants": [SAMPLE_VARIANT_SUMMARY], "total": 1}
        httpx_mock.add_response(url=url("/api/streams/v1/variants/"), json=payload)
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

    def test_passes_search(self, httpx_mock: HTTPXMock):
        payload = {"variants": [], "total": 0}
        httpx_mock.add_response(json=payload)
        list_variants(search="hero")
        req = httpx_mock.get_request()
        assert "search=hero" in str(req.url)


class TestListCollections:
    def test_returns_json(self, httpx_mock: HTTPXMock):
        payload = {"collections": [], "total": 0}
        httpx_mock.add_response(url=url("/api/streams/v1/collections/"), json=payload)
        result = json.loads(list_collections())
        assert result["total"] == 0

    def test_passes_search(self, httpx_mock: HTTPXMock):
        payload = {"collections": [], "total": 0}
        httpx_mock.add_response(json=payload)
        list_collections(search="ground")
        req = httpx_mock.get_request()
        assert "search=ground" in str(req.url)


class TestListBlocks:
    def test_returns_json(self, httpx_mock: HTTPXMock):
        payload = {"blocks": [], "total": 0}
        httpx_mock.add_response(url=url("/api/streams/v1/blocks/"), json=payload)
        result = json.loads(list_blocks())
        assert result["total"] == 0

    def test_passes_search(self, httpx_mock: HTTPXMock):
        payload = {"blocks": [], "total": 0}
        httpx_mock.add_response(json=payload)
        list_blocks(search="her")
        req = httpx_mock.get_request()
        assert "search=her" in str(req.url)


# ---------------------------------------------------------------------------
# Read tools
# ---------------------------------------------------------------------------


class TestGetCollection:
    def test_returns_collection_detail(self, httpx_mock: HTTPXMock):
        payload = {
            "id": 1,
            "identifier": "ground-state",
            "name": "Ground State",
            "description": "Minimal design system.",
            "template": "## Core Principles\n\nStructure dictates form.",
            "variant_count": 3,
        }
        httpx_mock.add_response(url=url("/api/streams/v1/collections/1/"), json=payload)
        result = json.loads(get_collection(1))
        assert result["identifier"] == "ground-state"
        assert result["template"] == "## Core Principles\n\nStructure dictates form."


class TestGetVariant:
    def test_includes_etag(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url=url("/api/streams/v1/variants/1/"),
            json=SAMPLE_VARIANT_DETAIL,
            headers={"ETag": 'W/"abc123"'},
        )
        result = json.loads(get_variant(1))
        assert result["html"] == "<div>hello</div>"
        assert result["_etag"] == 'W/"abc123"'


class TestGetContext:
    """The ``phoxtail_studio_get_context`` tool renders the context template."""

    CONTEXT_RESPONSE = {
        "block": {
            "identifier": "header_section",
            "name": "Header Section",
            "description": "A page header with title and subtitle.",
            "field_schema": '{"fields": []}',
        },
        "collection": {
            "identifier": "ground-state",
            "name": "Ground State",
            "description": "Minimal design system.",
            "design_guidelines": "## Core Principles\n\nStructure dictates form.",
        },
        "design_tokens": {
            "palette_roles": [
                {
                    "name": "Primary",
                    "identifier": "primary",
                    "description": "Main brand color.",
                },
            ],
            "font_roles": [
                {
                    "name": "Heading",
                    "identifier": "heading",
                    "description": "Used for headings.",
                },
            ],
        },
        "references": [],
    }

    def test_renders_context_template(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(json=self.CONTEXT_RESPONSE)
        result = get_context(block="header_section", collection="ground-state")
        assert "Header Section" in result
        assert "DTL Reference" in result
        assert "CSS Scoping" in result
        assert "Structure dictates form" in result
        assert "Primary" in result
        assert "primary" in result
        assert "Heading" in result
        assert "Design Tokens" in result

    def test_sends_references(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(json=self.CONTEXT_RESPONSE)
        get_context(
            block="header_section",
            collection="ground-state",
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
        result = diff_variant(1, html="<div>goodbye</div>")
        assert "--- a/html" in result
        assert "+++ b/html" in result
        assert "-<div>hello</div>" in result
        assert "+<div>goodbye</div>" in result

    def test_no_diff_when_unchanged(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            json=SAMPLE_VARIANT_DETAIL,
            headers={"ETag": 'W/"abc123"'},
        )
        result = diff_variant(1, html="<div>hello</div>")
        assert result == "(no differences)"

    def test_omitted_fields_not_diffed(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            json=SAMPLE_VARIANT_DETAIL,
            headers={"ETag": 'W/"abc123"'},
        )
        result = diff_variant(1, css=".hero { color: blue; }")
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
        result = json.loads(update_variant(1, etag='W/"abc123"', html="<div>new</div>"))
        assert result["html"] == "<div>new</div>"
        assert result["_etag"] == 'W/"new456"'

    def test_sends_if_match_header(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(json=SAMPLE_VARIANT_DETAIL, headers={"ETag": 'W/"x"'})
        update_variant(1, etag='W/"abc123"', html="x")
        req = httpx_mock.get_request()
        assert req.headers["If-Match"] == 'W/"abc123"'

    def test_conflict_returns_error_json(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            status_code=412,
            json={"detail": "ETag mismatch"},
        )
        result = json.loads(update_variant(1, etag='W/"stale"', html="x"))
        assert result["error"] == "conflict"

    def test_precondition_required(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            status_code=428,
            json={"detail": "If-Match required"},
        )
        result = json.loads(update_variant(1, etag="", html="x"))
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
# Block tools
# ---------------------------------------------------------------------------

SAMPLE_BLOCK_DETAIL = {
    "id": 1,
    "identifier": "stats",
    "name": "Stats",
    "description": "Data statistics display.",
    "group": "Data Display",
    "icon": "table",
    "is_shared": False,
    "variant_count": 0,
    "page_types": [],
    "variants": [],
    "field_schema": '[{"type": "char_field", "value": {"name": "title"}}]',
}


class TestGetBlock:
    def test_includes_etag(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url=url("/api/streams/v1/blocks/1/"),
            json=SAMPLE_BLOCK_DETAIL,
            headers={"ETag": 'W/"block123"'},
        )
        result = json.loads(get_block(1))
        assert result["identifier"] == "stats"
        assert result["field_schema"] is not None
        assert result["_etag"] == 'W/"block123"'


class TestCreateBlock:
    def test_success(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            status_code=201,
            json=SAMPLE_BLOCK_DETAIL,
            headers={"ETag": 'W/"new_block"'},
        )
        result = json.loads(
            create_block(
                identifier="stats",
                name="Stats",
                description="Data statistics display.",
                group="Data Display",
                icon="table",
                schema=[{"type": "char_field", "value": {"name": "title"}}],
            )
        )
        assert result["identifier"] == "stats"
        assert result["_etag"] == 'W/"new_block"'

    def test_sends_payload(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            status_code=201,
            json=SAMPLE_BLOCK_DETAIL,
            headers={"ETag": 'W/"x"'},
        )
        create_block(
            identifier="stats",
            name="Stats",
            schema=[{"type": "char_field", "value": {"name": "title"}}],
        )
        req = httpx_mock.get_request()
        body = json.loads(req.content)
        assert body["identifier"] == "stats"
        assert body["schema"] == [{"type": "char_field", "value": {"name": "title"}}]

    def test_conflict_existing(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            status_code=409,
            json={"detail": "Block 'stats' already exists."},
        )
        result = json.loads(create_block(identifier="stats", name="Stats"))
        assert result["error"] == "conflict"

    def test_validation_error(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            status_code=400,
            json={"detail": "schema: Invalid block type 'bad_field'."},
        )
        result = json.loads(
            create_block(
                identifier="bad",
                name="Bad",
                schema=[{"type": "bad_field", "value": {}}],
            )
        )
        assert result["error"] == "validation_error"


class TestUpdateBlock:
    def test_success(self, httpx_mock: HTTPXMock):
        updated = {**SAMPLE_BLOCK_DETAIL, "name": "Stats v2"}
        httpx_mock.add_response(
            json=updated,
            headers={"ETag": 'W/"updated"'},
        )
        result = json.loads(update_block(1, etag='W/"block123"', name="Stats v2"))
        assert result["name"] == "Stats v2"
        assert result["_etag"] == 'W/"updated"'

    def test_sends_if_match_header(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            json=SAMPLE_BLOCK_DETAIL,
            headers={"ETag": 'W/"x"'},
        )
        update_block(1, etag='W/"block123"', name="New Name")
        req = httpx_mock.get_request()
        assert req.headers["If-Match"] == 'W/"block123"'

    def test_conflict_returns_error(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            status_code=412,
            json={"detail": "ETag mismatch"},
        )
        result = json.loads(update_block(1, etag='W/"stale"', name="x"))
        assert result["error"] == "conflict"

    def test_precondition_required(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            status_code=428,
            json={"detail": "If-Match required"},
        )
        result = json.loads(update_block(1, etag="", name="x"))
        assert result["error"] == "precondition_required"

    def test_validation_error(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            status_code=400,
            json={"detail": "Invalid schema."},
        )
        result = json.loads(
            update_block(1, etag='W/"block123"', schema=[{"type": "bad", "value": {}}])
        )
        assert result["error"] == "validation_error"


# ---------------------------------------------------------------------------
# Resource and prompt
# ---------------------------------------------------------------------------

SAMPLE_CATALOG = {
    "common_parameters": {"name": {"type": "CharBlock"}},
    "field_types": {"char_field": {"label": "Char", "parameters": {}}},
    "structure_types": {"struct": {"label": "Struct", "parameters": {}}},
    "layer_types": {},
}


class TestSchemaResource:
    def test_returns_catalog_json(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(json=SAMPLE_CATALOG)
        result = json.loads(schema_reference())
        assert "field_types" in result
        assert "char_field" in result["field_types"]

    def test_registered(self):
        resources = mcp_server._resource_manager._resources
        assert "phoxtail://schema-reference" in resources


class TestDesignBlockPrompt:
    def test_renders_with_catalog(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(json=SAMPLE_CATALOG)
        result = design_block(description="A stats block for dashboards")
        assert "A stats block for dashboards" in result
        assert "Available Field Types" in result

    def test_renders_with_reference_url(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(json=SAMPLE_CATALOG)
        result = design_block(
            description="A stats block",
            reference_url="https://example.com/stats",
        )
        assert "https://example.com/stats" in result
        assert "Reference" in result

    def test_renders_without_reference_url(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(json=SAMPLE_CATALOG)
        result = design_block(description="A simple block")
        assert "Reference" not in result

    def test_registered(self):
        prompts = mcp_server._prompt_manager._prompts
        assert "design_block" in prompts


# ---------------------------------------------------------------------------
# CLI wiring
# ---------------------------------------------------------------------------


class TestServeCommand:
    """The ``phoxtail mcp serve`` command is registered and reachable."""

    def test_help_text(self):
        from phoxtail.__main__ import app as main_app

        result = runner.invoke(main_app, ["mcp", "serve", "--help"])
        assert result.exit_code == 0
        assert "MCP" in result.output or "stdio" in result.output
