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

import asyncio
import json

from pytest_httpx import HTTPXMock
from typer.testing import CliRunner

from phoxtail.mcp import mcp_server
from phoxtail.mcp._http import url
from phoxtail.mcp.content.pages import translate_page
from phoxtail.mcp.content.resources import locales_list
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
from phoxtail.mcp.studio.sessions import (
    commit_variant,
    discard_variant,
    list_sessions,
    open_variant,
    refresh_session,
)
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
    "block": {"id": 1, "identifier": "header_section", "name": "Header Section"},
    "collection": {"id": 1, "identifier": "general-unsorted", "name": "General (Unsorted)"},
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
            "phoxtail_studio_delete_collection",
            "phoxtail_studio_delete_block",
            "phoxtail_studio_delete_variant",
            "phoxtail_studio_list_shared_blocks",
            "phoxtail_studio_get_shared_block",
            "phoxtail_studio_create_shared_block",
            "phoxtail_studio_update_shared_block",
            "phoxtail_studio_delete_shared_block",
            "phoxtail_studio_render_block",
            "phoxtail_studio_screenshot_page",
            # Block category tools
            "phoxtail_studio_list_block_categories",
            "phoxtail_studio_get_block_category",
            "phoxtail_studio_create_block_category",
            "phoxtail_studio_update_block_category",
            "phoxtail_studio_delete_block_category",
            "phoxtail_studio_set_block_categories",
            "phoxtail_studio_add_block_category",
            "phoxtail_studio_remove_block_category",
            # Session-based editing tools
            "phoxtail_studio_open_variant",
            "phoxtail_studio_commit_variant",
            "phoxtail_studio_discard_variant",
            "phoxtail_studio_list_sessions",
            "phoxtail_studio_refresh_session",
        }
        pages_tools = {
            "phoxtail_locales_list",
            "phoxtail_page_types_list",
            "phoxtail_pages_list_pages",
            "phoxtail_pages_get_page",
            "phoxtail_pages_create_page",
            "phoxtail_pages_update_page",
            "phoxtail_pages_delete_page",
            "phoxtail_pages_publish",
            "phoxtail_pages_unpublish",
            "phoxtail_pages_translate_page",
            "phoxtail_pages_get_body",
            "phoxtail_pages_replace_body",
            "phoxtail_pages_get_block",
            "phoxtail_pages_update_block",
            "phoxtail_pages_add_block",
            "phoxtail_pages_delete_block",
            "phoxtail_pages_move_block",
            "phoxtail_pages_list_images",
            "phoxtail_pages_list_documents",
            "phoxtail_images_upload",
            "phoxtail_images_get",
            "phoxtail_images_view",
            "phoxtail_images_update",
            "phoxtail_images_delete",
            "phoxtail_documents_get",
            "phoxtail_documents_upload",
            "phoxtail_documents_update",
            "phoxtail_documents_delete",
            "phoxtail_videos_list",
            "phoxtail_videos_get",
            "phoxtail_videos_upload",
            "phoxtail_videos_update",
            "phoxtail_videos_delete",
            "phoxtail_audio_list",
            "phoxtail_audio_get",
            "phoxtail_audio_upload",
            "phoxtail_audio_update",
            "phoxtail_audio_delete",
        }
        content_tools = {
            "phoxtail_content_list_internal_links",
            "phoxtail_content_get_internal_link",
            "phoxtail_content_create_internal_link",
            "phoxtail_content_update_internal_link",
            "phoxtail_content_delete_internal_link",
            "phoxtail_collections_list",
            "phoxtail_collections_get",
            "phoxtail_collections_create",
            "phoxtail_collections_update",
            "phoxtail_collections_delete",
            "phoxtail_sites_list",
            "phoxtail_sites_get",
            "phoxtail_sites_create",
            "phoxtail_sites_update",
            "phoxtail_sites_delete",
        }
        cms_tools = {
            "phoxtail_site_settings_get",
            "phoxtail_site_settings_update",
            "phoxtail_site_settings_clear_image",
            "phoxtail_site_setting_fonts_list",
            "phoxtail_site_setting_fonts_get",
            "phoxtail_site_setting_fonts_add",
            "phoxtail_site_setting_fonts_update",
            "phoxtail_site_setting_fonts_remove",
            "phoxtail_site_setting_palettes_list",
            "phoxtail_site_setting_palettes_get",
            "phoxtail_site_setting_palettes_add",
            "phoxtail_site_setting_palettes_update",
            "phoxtail_site_setting_palettes_remove",
        }
        design_tools = {
            "phoxtail_palettes_list",
            "phoxtail_palettes_get",
            "phoxtail_palettes_create",
            "phoxtail_palettes_update",
            "phoxtail_palettes_delete",
            "phoxtail_palette_sets_list",
            "phoxtail_palette_sets_get",
            "phoxtail_palette_sets_create",
            "phoxtail_palette_sets_update",
            "phoxtail_palette_sets_delete",
            "phoxtail_palette_roles_list",
            "phoxtail_palette_roles_get",
            "phoxtail_palette_roles_create",
            "phoxtail_palette_roles_update",
            "phoxtail_palette_roles_delete",
            "phoxtail_font_families_list",
            "phoxtail_font_families_get",
            "phoxtail_font_families_create",
            "phoxtail_font_families_update",
            "phoxtail_font_families_delete",
            "phoxtail_font_roles_list",
            "phoxtail_font_roles_get",
            "phoxtail_font_roles_create",
            "phoxtail_font_roles_update",
            "phoxtail_font_roles_delete",
            "phoxtail_font_weights_list",
            "phoxtail_font_weights_get",
            "phoxtail_font_weights_upload",
            "phoxtail_font_weights_create_from_url",
            "phoxtail_font_weights_delete",
        }
        expected = studio_tools | pages_tools | content_tools | cms_tools | design_tools
        registered = {t.name for t in asyncio.run(mcp_server.list_tools())}
        # Optional installed apps contribute extra tools
        # via entry points; use subset check so those don't cause false failures.
        assert expected <= registered


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
        list_variants(block="hero", collection="general-unsorted")
        req = httpx_mock.get_request()
        assert "block=hero" in str(req.url)
        assert "collection=general-unsorted" in str(req.url)

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
            "identifier": "general-unsorted",
            "name": "General (Unsorted)",
            "description": "Minimal design system.",
            "variant_count": 3,
        }
        httpx_mock.add_response(url=url("/api/streams/v1/collections/1/"), json=payload)
        result = json.loads(get_collection(1))
        assert result["identifier"] == "general-unsorted"
        assert result["name"] == "General (Unsorted)"


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
            "identifier": "general-unsorted",
            "name": "General (Unsorted)",
            "description": "Minimal design system.",
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
        result = get_context(block_id=1, collection_id=1)
        assert "Header Section" in result
        assert "DTL Reference" in result
        assert "CSS Scoping" in result
        assert "Primary" in result
        assert "primary" in result
        assert "Heading" in result
        assert "Design Tokens" in result

    def test_sends_references(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(json=self.CONTEXT_RESPONSE)
        get_context(
            block_id=1,
            collection_id=1,
            references=[5, 7],
        )
        req = httpx_mock.get_request()
        body = json.loads(req.content)
        assert body["references"] == [5, 7]


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
                block_id=1,
                collection_id=1,
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
                block_id=1,
                collection_id=1,
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
                block_id=999,
                collection_id=1,
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
        result = json.loads(update_block(1, etag='W/"block123"', schema=[{"type": "bad", "value": {}}]))
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
        resources = {str(r.uri) for r in asyncio.run(mcp_server.list_resources())}
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
        prompts = {p.name for p in asyncio.run(mcp_server.list_prompts())}
        assert "design_block" in prompts


# ---------------------------------------------------------------------------
# phoxtail_locales_list
# ---------------------------------------------------------------------------


class TestLocalesList:
    def test_returns_json(self, httpx_mock: HTTPXMock):
        payload = {
            "locales": [
                {"id": 1, "language_code": "en"},
                {"id": 2, "language_code": "de"},
            ],
            "total": 2,
        }
        httpx_mock.add_response(url=url("/api/content/v1/locales/"), json=payload)
        result = json.loads(locales_list())
        assert result["total"] == 2
        assert result["locales"][0]["language_code"] == "en"

    def test_error_surfaces_as_envelope(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(status_code=500, json={"detail": "boom"})
        result = json.loads(locales_list())
        assert result["error"] == "http_error"
        assert result["status"] == 500


# ---------------------------------------------------------------------------
# phoxtail_pages_translate_page
# ---------------------------------------------------------------------------

SAMPLE_PAGE_DETAIL = {
    "id": 42,
    "title": "Home (DE)",
    "slug": "home-de",
    "live": False,
    "locale": "de",
    "content_type": "phoxtail_core.HomePage",
    "url": None,
}


class TestTranslatePage:
    def test_success_returns_page_with_etag(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url=url("/api/content/v1/pages/10/copy_for_translation/"),
            status_code=201,
            json=SAMPLE_PAGE_DETAIL,
            headers={"ETag": 'W/"abc123"'},
        )
        result = json.loads(translate_page(page_id=10, locale_id=2))
        assert result["id"] == 42
        assert result["locale"] == "de"
        assert result["_etag"] == 'W/"abc123"'

    def test_sends_correct_payload(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(status_code=201, json=SAMPLE_PAGE_DETAIL)
        translate_page(
            page_id=10,
            locale_id=2,
            copy_parents=True,
            alias=False,
            include_subtree=True,
        )
        req = httpx_mock.get_request()
        body = json.loads(req.content)
        assert body["locale"] == 2
        assert body["copy_parents"] is True
        assert body["include_subtree"] is True

    def test_already_translated_returns_409_envelope(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            status_code=409,
            json={"detail": "Page already has a translation in locale 'de'."},
        )
        result = json.loads(translate_page(page_id=10, locale_id=2))
        assert result["error"] == "conflict"
        assert result["status"] == 409

    def test_parent_not_translated_returns_400_envelope(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            status_code=400,
            json={"detail": "Parent page is not translated into the target locale."},
        )
        result = json.loads(translate_page(page_id=10, locale_id=2))
        assert result["error"] == "validation_error"
        assert result["status"] == 400

    def test_permission_denied_returns_403_envelope(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            status_code=403,
            json={"detail": "You do not have permission to submit a translation."},
        )
        result = json.loads(translate_page(page_id=10, locale_id=2))
        assert result["error"] == "permission_denied"
        assert result["status"] == 403


# ---------------------------------------------------------------------------
# Session-based editing tools
# ---------------------------------------------------------------------------


class TestOpenVariant:
    def test_opens_new_session(self, httpx_mock: HTTPXMock, tmp_path, monkeypatch):
        httpx_mock.add_response(
            url=url("/api/streams/v1/variants/1/"),
            json=SAMPLE_VARIANT_DETAIL,
            headers={"ETag": 'W/"abc123"'},
        )
        # Context fetch — allow it to fail silently
        httpx_mock.add_response(
            url=url("/api/streams/v1/context/"),
            status_code=500,
            json={"detail": "unavailable"},
        )
        monkeypatch.setattr(
            "phoxtail.cli.studio.session.sessions_root",
            lambda: tmp_path / ".phoxtail-sessions",
        )
        result = json.loads(open_variant(1))
        assert result["status"] == "opened"
        assert result["session_id"] == "1"
        assert "html" in result["files"]
        assert "css" in result["files"]
        assert "javascript" in result["files"]
        assert "next_steps" in result

    def test_paths_are_relative_to_the_project_root(self, httpx_mock: HTTPXMock, tmp_path, monkeypatch):
        """The MCP server may run in a container where the project root is
        /app — only a project-root-relative path is valid for the agent."""
        httpx_mock.add_response(
            url=url("/api/streams/v1/variants/1/"),
            json=SAMPLE_VARIANT_DETAIL,
            headers={"ETag": 'W/"abc123"'},
        )
        httpx_mock.add_response(
            url=url("/api/streams/v1/context/"),
            status_code=500,
            json={"detail": "unavailable"},
        )
        # Resolved: _rel anchors on Path.cwd(), which resolves symlinks —
        # an unresolved tmp_path would not be relative to it where /tmp is one.
        monkeypatch.setattr(
            "phoxtail.cli.studio.session.sessions_root",
            lambda: tmp_path.resolve() / ".phoxtail-sessions",
        )
        result = json.loads(open_variant(1))
        assert result["path"] == ".phoxtail-sessions/1"
        assert result["files"]["css"] == ".phoxtail-sessions/1/style.css"
        assert not any(p.startswith("/") for p in result["files"].values())

    def test_idempotent_when_already_open(self, httpx_mock: HTTPXMock, tmp_path, monkeypatch):
        httpx_mock.add_response(
            url=url("/api/streams/v1/variants/1/"),
            json=SAMPLE_VARIANT_DETAIL,
            headers={"ETag": 'W/"abc123"'},
        )
        httpx_mock.add_response(
            url=url("/api/streams/v1/context/"),
            status_code=500,
            json={"detail": "unavailable"},
        )
        monkeypatch.setattr(
            "phoxtail.cli.studio.session.sessions_root",
            lambda: tmp_path / ".phoxtail-sessions",
        )
        # Open once
        open_variant(1)

        # Second GET for the idempotent open
        httpx_mock.add_response(
            url=url("/api/streams/v1/variants/1/"),
            json=SAMPLE_VARIANT_DETAIL,
            headers={"ETag": 'W/"abc123"'},
        )
        result = json.loads(open_variant(1))
        assert result["status"] == "already_open"
        assert result["session_id"] == "1"


class TestCommitVariant:
    def test_success(self, httpx_mock: HTTPXMock, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "phoxtail.cli.studio.session.sessions_root",
            lambda: tmp_path / ".phoxtail-sessions",
        )
        # Seed a session on disk
        from phoxtail.cli.studio import session as _sess

        _sess.create_session(
            session_id="1",
            variant_data=SAMPLE_VARIANT_DETAIL,
            context_md="",
            template_used="context",
            etag='W/"abc123"',
        )

        updated = {**SAMPLE_VARIANT_DETAIL, "html": "<div>updated</div>"}
        httpx_mock.add_response(
            json=updated,
            headers={"ETag": 'W/"new456"'},
        )
        result = json.loads(commit_variant(session_id="1"))
        assert result["status"] == "committed"
        assert result["_etag"] == 'W/"new456"'
        assert result["session_cleaned"] is False

    def test_commit_conflict_412(self, httpx_mock: HTTPXMock, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "phoxtail.cli.studio.session.sessions_root",
            lambda: tmp_path / ".phoxtail-sessions",
        )
        from phoxtail.cli.studio import session as _sess

        _sess.create_session(
            session_id="1",
            variant_data=SAMPLE_VARIANT_DETAIL,
            context_md="",
            template_used="context",
            etag='W/"stale"',
        )
        httpx_mock.add_response(status_code=412, json={"detail": "ETag mismatch"})
        result = json.loads(commit_variant(session_id="1"))
        assert result["error"] == "conflict"

    def test_no_active_sessions(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "phoxtail.cli.studio.session.sessions_root",
            lambda: tmp_path / ".phoxtail-sessions",
        )
        result = json.loads(commit_variant())
        assert result["error"] == "no_sessions"


class TestDiscardVariant:
    def test_success(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "phoxtail.cli.studio.session.sessions_root",
            lambda: tmp_path / ".phoxtail-sessions",
        )
        from phoxtail.cli.studio import session as _sess

        _sess.create_session(
            session_id="1",
            variant_data=SAMPLE_VARIANT_DETAIL,
            context_md="",
            template_used="context",
            etag='W/"abc"',
        )
        result = json.loads(discard_variant(session_id="1"))
        assert result["status"] == "discarded"
        assert not _sess.session_exists("1")

    def test_not_found(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "phoxtail.cli.studio.session.sessions_root",
            lambda: tmp_path / ".phoxtail-sessions",
        )
        result = json.loads(discard_variant(session_id="nonexistent"))
        assert result["error"] == "not_found"

    def test_rejects_path_traversal(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "phoxtail.cli.studio.session.sessions_root",
            lambda: tmp_path / ".phoxtail-sessions",
        )
        result = json.loads(discard_variant(session_id="../../etc"))
        assert result["error"] == "invalid_session_id"


class TestListSessions:
    def test_empty(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "phoxtail.cli.studio.session.sessions_root",
            lambda: tmp_path / ".phoxtail-sessions",
        )
        result = json.loads(list_sessions())
        assert result["total"] == 0
        assert result["sessions"] == []

    def test_with_sessions(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "phoxtail.cli.studio.session.sessions_root",
            lambda: tmp_path.resolve() / ".phoxtail-sessions",
        )
        from phoxtail.cli.studio import session as _sess

        _sess.create_session(
            session_id="1",
            variant_data=SAMPLE_VARIANT_DETAIL,
            context_md="",
            template_used="context",
            etag='W/"abc"',
        )
        result = json.loads(list_sessions())
        assert result["total"] == 1
        assert result["sessions"][0]["session_id"] == "1"
        assert result["sessions"][0]["path"] == ".phoxtail-sessions/1"


class TestRefreshSession:
    def test_success(self, httpx_mock: HTTPXMock, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "phoxtail.cli.studio.session.sessions_root",
            lambda: tmp_path / ".phoxtail-sessions",
        )
        from phoxtail.cli.studio import session as _sess

        _sess.create_session(
            session_id="1",
            variant_data=SAMPLE_VARIANT_DETAIL,
            context_md="",
            template_used="context",
            etag='W/"old"',
        )
        httpx_mock.add_response(
            url=url("/api/streams/v1/variants/1/"),
            json=SAMPLE_VARIANT_DETAIL,
            headers={"ETag": 'W/"refreshed"'},
        )
        result = json.loads(refresh_session(session_id="1"))
        assert result["status"] == "refreshed"
        assert result["_etag"] == 'W/"refreshed"'

        updated_meta = _sess.read_session("1")
        assert updated_meta["etag"] == 'W/"refreshed"'


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
