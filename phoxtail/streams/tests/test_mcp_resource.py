"""Tests for MCP resources and prompts that require Django/Wagtail settings.

These tests import Wagtail schema blocks (which need Django settings) so
they run as part of the engine test suite (``make test-engine``), not the
CLI tests (``make test-cli -p no:django``).
"""

from __future__ import annotations

from phoxtail.streams.api.v1.schema_catalog import get_schema_catalog


class TestSchemaCatalog:
    def test_has_common_parameters(self):
        catalog = get_schema_catalog()
        common = catalog["common_parameters"]
        assert "name" in common
        assert "required" in common
        assert "help_text" in common
        assert "icon" in common

    def test_has_field_types(self):
        catalog = get_schema_catalog()
        assert "char_field" in catalog["field_types"]
        char = catalog["field_types"]["char_field"]
        assert "label" in char
        assert "parameters" in char

    def test_has_structure_types(self):
        catalog = get_schema_catalog()
        structs = catalog["structure_types"]
        assert "struct" in structs
        assert "list_struct" in structs
        assert "list_field" in structs

    def test_has_layer_types(self):
        catalog = get_schema_catalog()
        assert len(catalog["layer_types"]) > 0
