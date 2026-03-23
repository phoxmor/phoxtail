"""Tests for cli.utils.env."""

from phoxtail.cli.utils.env import read_env_value


class TestReadEnvValue:
    def test_returns_value_for_existing_key(self, env_file):
        path = env_file("DOMAIN=example.com\nSECRET_KEY=abc123")
        assert read_env_value("DOMAIN", env_file=path) == "example.com"
        assert read_env_value("SECRET_KEY", env_file=path) == "abc123"

    def test_returns_none_for_missing_key(self, env_file):
        path = env_file("DOMAIN=example.com")
        assert read_env_value("MISSING_KEY", env_file=path) is None

    def test_returns_none_for_missing_file(self, tmp_path):
        path = tmp_path / "nonexistent.env"
        assert read_env_value("DOMAIN", env_file=path) is None

    def test_strips_double_quotes(self, env_file):
        path = env_file('DOMAIN="example.com"')
        assert read_env_value("DOMAIN", env_file=path) == "example.com"

    def test_strips_single_quotes(self, env_file):
        path = env_file("DOMAIN='example.com'")
        assert read_env_value("DOMAIN", env_file=path) == "example.com"

    def test_ignores_commented_lines(self, env_file):
        path = env_file("# DOMAIN=old.com\nDOMAIN=example.com")
        assert read_env_value("DOMAIN", env_file=path) == "example.com"

    def test_returns_none_for_empty_value(self, env_file):
        path = env_file("DOMAIN=")
        assert read_env_value("DOMAIN", env_file=path) is None

    def test_handles_value_with_equals_sign(self, env_file):
        path = env_file("SECRET_KEY=abc=def=ghi")
        assert read_env_value("SECRET_KEY", env_file=path) == "abc=def=ghi"

    def test_handles_spaces_around_key(self, env_file):
        path = env_file("  DOMAIN = example.com  ")
        assert read_env_value("DOMAIN", env_file=path) == "example.com"

    def test_returns_first_match(self, env_file):
        path = env_file("DOMAIN=first.com\nDOMAIN=second.com")
        assert read_env_value("DOMAIN", env_file=path) == "first.com"

    def test_boolean_value(self, env_file):
        path = env_file("FEATURE_ACTIVATE_BOOKING=true")
        result = read_env_value("FEATURE_ACTIVATE_BOOKING", env_file=path)
        assert result == "true"
