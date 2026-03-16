"""Tests for cli.commands.db hostname localization."""

import json

from phoxtail.commands.db import _deep_localize, _localize_hostnames


class TestDeepLocalize:
    """Tests for _deep_localize — recursive hostname replacement."""

    def setup_method(self):
        self.hostname_map = {
            "example.com": "localhost",
            "blog.example.com": "blog.localhost",
        }

    def test_replaces_natural_key(self):
        val = ["example.com", 80]
        result = _deep_localize(val, self.hostname_map)
        assert result == ["localhost", 80]

    def test_ignores_non_matching_natural_key(self):
        val = ["other.com", 80]
        result = _deep_localize(val, self.hostname_map)
        assert result == ["other.com", 80]

    def test_replaces_in_nested_dict(self):
        val = {"site": {"ref": ["example.com", 80]}}
        result = _deep_localize(val, self.hostname_map)
        assert result == {"site": {"ref": ["localhost", 80]}}

    def test_replaces_in_json_encoded_string(self):
        inner = json.dumps({"ref": ["blog.example.com", 80]})
        result = _deep_localize(inner, self.hostname_map)
        parsed = json.loads(result)
        assert parsed == {"ref": ["blog.localhost", 80]}

    def test_leaves_plain_strings_unchanged(self):
        assert _deep_localize("hello", self.hostname_map) == "hello"

    def test_leaves_non_json_curly_strings_unchanged(self):
        val = "{not valid json"
        assert _deep_localize(val, self.hostname_map) == val

    def test_leaves_integers_unchanged(self):
        assert _deep_localize(42, self.hostname_map) == 42

    def test_handles_empty_hostname_map(self):
        val = ["example.com", 80]
        result = _deep_localize(val, {})
        assert result == ["example.com", 80]

    def test_list_longer_than_two_is_recursed(self):
        val = [["example.com", 80], ["blog.example.com", 80]]
        result = _deep_localize(val, self.hostname_map)
        assert result == [["localhost", 80], ["blog.localhost", 80]]


class TestLocalizeHostnames:
    """Tests for _localize_hostnames — full fixture transformation."""

    def test_rewrites_root_domain(self, sample_fixture_data):
        result = _localize_hostnames(sample_fixture_data, "localhost")
        sites = [e for e in result if e["model"] == "wagtailcore.site"]
        assert sites[0]["fields"]["hostname"] == "localhost"

    def test_preserves_subdomain(self, sample_fixture_data):
        result = _localize_hostnames(sample_fixture_data, "localhost")
        sites = [e for e in result if e["model"] == "wagtailcore.site"]
        assert sites[1]["fields"]["hostname"] == "blog.localhost"

    def test_rewrites_natural_key_references(self, sample_fixture_data):
        result = _localize_hostnames(sample_fixture_data, "localhost")
        page = [e for e in result if e["model"] == "wagtailcore.page"][0]
        assert page["fields"]["owner"] == ["localhost", 80]

    def test_noop_when_already_target_domain(self):
        data = [
            {
                "model": "wagtailcore.site",
                "pk": 1,
                "fields": {"hostname": "localhost", "port": 80},
            }
        ]
        result = _localize_hostnames(data, "localhost")
        assert result[0]["fields"]["hostname"] == "localhost"

    def test_skips_ip_addresses(self):
        data = [
            {
                "model": "wagtailcore.site",
                "pk": 1,
                "fields": {"hostname": "192.168.1.1", "port": 80},
            }
        ]
        result = _localize_hostnames(data, "localhost")
        assert result[0]["fields"]["hostname"] == "192.168.1.1"

    def test_skips_entries_ending_with_target_domain(self):
        data = [
            {
                "model": "wagtailcore.site",
                "pk": 1,
                "fields": {"hostname": "blog.localhost", "port": 80},
            }
        ]
        result = _localize_hostnames(data, "localhost")
        assert result[0]["fields"]["hostname"] == "blog.localhost"

    def test_handles_json_in_string_fields(self):
        data = [
            {
                "model": "wagtailcore.site",
                "pk": 1,
                "fields": {"hostname": "example.com", "port": 80},
            },
            {
                "model": "wagtailcore.page",
                "pk": 1,
                "fields": {
                    "body": json.dumps({"ref": ["example.com", 80]}),
                },
            },
        ]
        result = _localize_hostnames(data, "localhost")
        body = json.loads(result[1]["fields"]["body"])
        assert body["ref"] == ["localhost", 80]
