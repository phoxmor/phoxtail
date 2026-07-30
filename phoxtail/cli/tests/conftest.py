"""Shared fixtures for CLI tests."""

import pytest

from phoxtail.cli.utils import net as net_utils
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


@pytest.fixture(autouse=True)
def isolated_net_dir(tmp_path, monkeypatch):
    """Keep the shared net's host-side state out of the developer's real home.

    ``net attach`` writes the members file, so without this a test run would
    edit the actual ``~/.phoxtail/net/members.json`` and leave temp-dir
    projects in it. Redirecting ``NET_DIR`` is enough because
    :func:`~phoxtail.cli.utils.net.members_file` resolves it per call.

    The empty members file matters as much as the redirect: absent one,
    ``read_members`` falls back to recovering membership from container
    labels, which shells out to the developer's real Docker and would make
    any test touching ``peers``/``up``/``down`` depend on host state.
    """
    net_dir = tmp_path / "phoxtail-home" / "net"
    monkeypatch.setattr(net_utils, "NET_DIR", net_dir)
    net_dir.mkdir(parents=True, exist_ok=True)
    (net_dir / "members.json").write_text('{"projects": []}\n')


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
