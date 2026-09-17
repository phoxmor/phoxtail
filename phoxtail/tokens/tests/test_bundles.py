"""Outsiders are given bundles; bundles are read off the doors.

A codename is a row a migration may rewrite; a scope an outside client
stored is a promise. So a client asks for ``cms:read`` and phoxtail turns
that into codenames when the credential is read. What these pin is that
the table behind that name is derived from what the doors actually ask,
that every name in it stands for something real, and that the two
documents a client reads — the authorization server's card and the MCP
server's resource document — say the same thing.
"""

import json
import re
from pathlib import Path

import pytest
from django.conf import settings
from django.contrib.auth.models import Permission
from django.test import override_settings

from phoxtail.tokens import bundles

# The table is read off every installed app's doors, and a door in one app
# may name a codename of another, so what it says is only the project's
# table under the project's app set — the shared one, not this app's own
# narrower settings.
pytestmark = pytest.mark.skipif(
    "phoxtail.agent" not in settings.INSTALLED_APPS,
    reason="the bundles are derived from every phoxtail app's doors",
)


@pytest.fixture(autouse=True)
def fresh_table():
    bundles.derive.cache_clear()
    yield
    bundles.derive.cache_clear()


class TestTheTableComesFromTheDoors:
    def test_an_endpoints_codename_lands_in_its_apps_bundle(self):
        """``wagtailcore.view_page`` is Wagtail's permission, named by a cms
        endpoint: it belongs to the cms bundle, not to a bundle that does
        not exist for wagtailcore."""
        table = bundles.derive()
        assert "wagtailcore.view_page" in table["cms:read"]
        assert "wagtailcore.publish_page" in table["cms:write"]
        assert not any(name.startswith("wagtailcore") for name in table)

    def test_a_tools_codename_lands_too(self):
        """One codename is named by a streams tool and by no endpoint at
        all; a table read from endpoints alone would offer a tool no
        bundle could ever unlock."""
        assert "phoxtail_agent.access_chatbot" in bundles.derive()["streams:write"]

    def test_write_carries_read(self):
        table = bundles.derive()
        for name, codenames in table.items():
            app, _, act = name.partition(":")
            if act == bundles.WRITE and f"{app}:{bundles.READ}" in table:
                assert table[f"{app}:{bundles.READ}"] <= codenames

    def test_read_is_only_looking(self):
        for name, codenames in bundles.derive().items():
            if name.endswith(":read"):
                assert all(bundles.is_read(c) for c in codenames)

    def test_no_bundle_is_empty(self):
        assert all(bundles.derive().values())

    def test_nothing_a_door_names_is_dropped(self):
        """The derivation attributes each tool to an app by its module; a
        tool it could not place would vanish from every bundle and every
        other assertion here would still pass. Read the codenames off the
        source, the way the per-app tool tests do, and demand the union."""
        root = Path(bundles.__file__).resolve().parents[1]
        named = set()
        for surface in ("api", "mcp"):
            for path in root.glob(f"*/{surface}/**/*.py"):
                if "tests" in path.parts:
                    continue
                # A door may name several codenames in one call.
                for arguments in re.findall(r"(?:guarded|scoped)\(([^)]*)\)", path.read_text()):
                    named.update(re.findall(r'"([a-z_]+\.[a-z_]+)"', arguments))
        assert set().union(*bundles.derive().values()) == named

    @pytest.mark.django_db
    def test_every_codename_names_a_real_permission(self):
        """The failure this vocabulary exists to prevent, checked on our own
        side: a bundle that expands to a codename no row carries would grant
        nothing silently."""
        known = {f"{a}.{c}" for a, c in Permission.objects.values_list("content_type__app_label", "codename")}
        for name, codenames in bundles.derive().items():
            assert codenames <= known, name


class TestExpansion:
    def test_expands_to_the_union(self):
        table = bundles.derive()
        assert bundles.expand(["cms:read", "media:read"]) == table["cms:read"] | table["media:read"]

    def test_a_codename_stands_for_itself(self):
        """A key may carry both vocabularies; only a bundle is looked up."""
        assert bundles.expand(["wagtailcore.publish_page"]) == {"wagtailcore.publish_page"}
        table = bundles.derive()
        assert bundles.expand(["cms:read", "wagtailcore.publish_page"]) == table["cms:read"] | {
            "wagtailcore.publish_page"
        }

    def test_a_bundle_that_no_longer_exists_opens_nothing(self):
        """Not in the table, so not a bundle: it passes through as a name,
        and no door asks for a name spelt like that. Same outcome as
        expanding to nothing, with no pattern consulted."""
        assert not bundles.is_bundle("gone:read")
        assert bundles.expand(["gone:read"]) == {"gone:read"}
        assert bundles.expand([]) == set()


class TestTheBackend:
    def test_every_available_scope_has_a_description(self):
        """The consent screen indexes descriptions by the requested scope; a
        scope that validates without one is a crash at the moment a person
        is approving."""
        backend = bundles.Bundles()
        described = backend.get_all_scopes()
        assert set(backend.get_available_scopes()) == set(described)
        assert all(described.values())

    def test_descriptions_read_as_a_sentence_about_the_app(self):
        assert bundles.describe("cms:read") == "Read Phoxtail CMS"
        assert bundles.describe("cms:write") == "Read and change Phoxtail CMS"

    def test_nothing_is_granted_by_default(self):
        assert bundles.Bundles().get_default_scopes() == []


ISSUER_HOST = "t.localhost"


@pytest.fixture
def site(tmp_path, monkeypatch, settings):
    toml = tmp_path / "phoxtail.toml"
    toml.write_text(f'[project]\nname = "t"\n\n[studio]\napi_url = "http://{ISSUER_HOST}"\n')
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("DOMAIN", raising=False)
    from phoxtail.cli.utils.config import load_config
    from phoxtail.tokens.provider import defaults

    load_config.cache_clear()
    settings.ROOT_URLCONF = "phoxtail.tokens.tests.discovery_urls"
    settings.ALLOWED_HOSTS = [ISSUER_HOST]
    with override_settings(OAUTH2_PROVIDER=defaults()):
        yield
    load_config.cache_clear()


@pytest.mark.django_db
class TestTheTwoDocumentsAgree:
    def test_the_card_lists_every_bundle_and_nothing_else(self, client, site):
        response = client.get("/.well-known/oauth-authorization-server", HTTP_HOST=ISSUER_HOST)
        card = json.loads(response.content)
        assert card["scopes_supported"] == sorted(bundles.derive())
        assert "read" not in card["scopes_supported"]

    def test_the_resource_document_lists_the_same(self, site):
        from phoxtail.cli.mcp import front_door

        auth, _ = front_door()
        assert set(auth.scopes_supported) == set(bundles.derive())
