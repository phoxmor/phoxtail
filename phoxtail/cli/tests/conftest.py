"""Shared fixtures for CLI tests."""

import pytest

from phoxtail.cli.utils.config import load_config

SAMPLE_TOML = """\
[project]
name = "phoxtail"

[db.clusters.cms]
apps = [
    "auth.Group",
    "users",
    "wagtailcore.Page",
]

[db.clusters.booking]
apps = [
    "booking_core",
]
depends_on = ["cms"]
"""


@pytest.fixture(autouse=True)
def project_dir(tmp_path, monkeypatch):
    """Create a temporary phoxtail project directory with phoxtail.toml.

    Changes cwd to the temp dir and clears the config cache so each test
    gets a fresh load.
    """
    toml_path = tmp_path / "phoxtail.toml"
    toml_path.write_text(SAMPLE_TOML)
    monkeypatch.chdir(tmp_path)
    load_config.cache_clear()
    yield tmp_path
    load_config.cache_clear()


@pytest.fixture
def env_file(tmp_path):
    """Create a temporary .env file and return a writer helper.

    Usage:
        def test_something(env_file):
            path = env_file("DOMAIN=example.com\\nSECRET_KEY=abc")
            # path is a Path object pointing to the written file
    """

    def _write(content: str):
        path = tmp_path / ".env"
        path.write_text(content)
        return path

    return _write


@pytest.fixture
def sample_fixture_data():
    """Minimal Wagtail dumpdata fixture for hostname localization tests."""
    return [
        {
            "model": "wagtailcore.site",
            "pk": 1,
            "fields": {
                "hostname": "example.com",
                "port": 80,
                "site_name": "Example",
                "root_page": 1,
                "is_default_site": True,
            },
        },
        {
            "model": "wagtailcore.site",
            "pk": 2,
            "fields": {
                "hostname": "blog.example.com",
                "port": 80,
                "site_name": "Blog",
                "root_page": 2,
                "is_default_site": False,
            },
        },
        {
            "model": "wagtailcore.page",
            "pk": 1,
            "fields": {
                "title": "Home",
                "slug": "home",
                "owner": ["example.com", 80],
            },
        },
    ]
