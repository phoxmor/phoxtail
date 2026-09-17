"""A key the authorization server issued is read like any other.

The API answered ``401`` to such a key: it was found by digest in a table
the API never looked in, and it carried bundles where the doors ask
codenames. Now one header is routed by its shape to one table, and every
key is read into the same credential — names as stored, scopes as the
codenames those names mean today. Nothing behind the door can tell which
table a key came from, and these pin that both the routing and the
reading hold.
"""

import json
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.conf import settings
from django.test import RequestFactory, override_settings
from django.utils import timezone

from phoxtail.core.authorization import AuthorizationContext
from phoxtail.tokens import bundles
from phoxtail.tokens.constants import PHOXTAIL_TOKEN_PREFIX
from phoxtail.tokens.ninja import PhoxtailTokenAuth
from phoxtail.tokens.services.admin.operations.create import _generate_raw_token

from .conftest import issue_key as _issue
from .factories import AccessTokenFactory, UserFactory

HOST = "t.localhost"

# A key is spent at doors every app declares and reported for a person
# phoxtail's user model names by uuid, so this is the project's behaviour
# only under the project's app set — the shared settings, not this app's
# narrower ones.
pytestmark = [
    pytest.mark.django_db,
    pytest.mark.skipif(
        "phoxtail.agent" not in settings.INSTALLED_APPS,
        reason="reads keys against every phoxtail app's doors and phoxtail's user model",
    ),
]


@pytest.fixture
def site(tmp_path, monkeypatch, settings):
    toml = tmp_path / "phoxtail.toml"
    toml.write_text(f'[project]\nname = "t"\n\n[studio]\napi_url = "http://{HOST}"\n')
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("DOMAIN", raising=False)
    from phoxtail.cli.utils.config import load_config
    from phoxtail.tokens.provider import defaults

    load_config.cache_clear()
    settings.ROOT_URLCONF = "phoxtail.tokens.tests.site_urls"
    settings.ALLOWED_HOSTS = [HOST]
    with override_settings(OAUTH2_PROVIDER=defaults()):
        yield
    load_config.cache_clear()


def _resolve(raw, path="/api/whoami/"):
    """What the backend makes of a bearer. The header goes on the request
    as well as into the call: ninja hands the backend the header's value,
    and the authorization server's core reads it off the request itself."""
    request = RequestFactory().get(path, HTTP_HOST=HOST, HTTP_AUTHORIZATION=f"Bearer {raw}")
    return PhoxtailTokenAuth().authenticate(request, f"Bearer {raw}")


class TestTheRoute:
    def test_a_phoxtail_key_never_asks_the_authorization_server(self, site):
        token = AccessTokenFactory(unrestricted=True)
        with patch("phoxtail.tokens.ninja.issued_credential") as issued:
            context = _resolve(token._raw_token)
        assert context.token.row == token
        issued.assert_not_called()

    def test_an_issued_key_never_looks_in_phoxtails_table(self, site):
        raw, token = _issue(UserFactory())
        with patch("phoxtail.tokens.ninja.authenticate") as own:
            context = _resolve(raw)
        assert context.token.row == token
        own.assert_not_called()

    def test_a_forged_prefix_earns_no_second_chance(self, site):
        """A key wearing phoxtail's prefix that phoxtail did not mint is
        refused where it claims to belong, not retried elsewhere."""
        with patch("phoxtail.tokens.ninja.issued_credential") as issued:
            assert _resolve(f"{PHOXTAIL_TOKEN_PREFIX}notminted") is None
        issued.assert_not_called()


class TestTheShapeIsTheContract:
    """The route reads five characters. These fail if the shape of either
    kind of key ever moves without the route moving with it."""

    def test_the_minter_and_the_route_share_the_prefix(self):
        assert _generate_raw_token().startswith(PHOXTAIL_TOKEN_PREFIX)

    def test_the_authorization_servers_keys_cannot_wear_it(self):
        """Read off the library, not assumed: its alphabet has no
        underscore, so no key it mints can begin with ours."""
        from oauthlib.common import UNICODE_ASCII_CHARACTER_SET, generate_token

        assert "_" not in UNICODE_ASCII_CHARACTER_SET
        assert not generate_token().startswith(PHOXTAIL_TOKEN_PREFIX)


class TestOneReader:
    def test_an_issued_key_reads_as_its_bundles_codenames(self, site):
        raw, token = _issue(UserFactory(), scope="cms:read media:write")
        context = _resolve(raw)
        table = bundles.derive()
        assert isinstance(context, AuthorizationContext)
        assert context.user == token.user
        assert context.token.names == ("cms:read", "media:write")
        assert context.token.scopes == table["cms:read"] | table["media:write"]
        assert context.token.unrestricted is False
        assert context.token.expires_at == token.expires

    def test_a_phoxtail_key_may_carry_both_vocabularies(self, site):
        token = AccessTokenFactory(unrestricted=False, scopes=["cms:read", "wagtailcore.publish_page"])
        context = _resolve(token._raw_token)
        assert context.token.scopes == bundles.derive()["cms:read"] | {"wagtailcore.publish_page"}

    def test_the_doors_cannot_tell_the_two_apart(self, site):
        from phoxtail.api.auth import has_scope

        raw, _ = _issue(UserFactory(), scope="cms:read")
        issued = _resolve(raw)
        own = _resolve(AccessTokenFactory(unrestricted=False, scopes=["cms:read"])._raw_token)
        for context in (issued, own):
            assert has_scope("wagtailcore.view_page")(context)
            assert not has_scope("wagtailcore.change_page")(context)

    def test_an_expired_issued_key_is_refused(self, site):
        raw, _ = _issue(UserFactory(), expires=timezone.now() - timedelta(seconds=1))
        assert _resolve(raw) is None

    def test_a_key_for_another_door_is_refused(self, site):
        """The site's own origin is not the door, and neither is another
        host's door — a key that names either opens nothing here."""
        for elsewhere in ("http://t.localhost/", "http://mcp.other.localhost/mcp", "http://t.localhost/mcp"):
            raw, _ = _issue(UserFactory(), resource=[elsewhere])
            assert _resolve(raw) is None, elsewhere


class TestTheAudience:
    """A key names the door it was minted for; the API stands behind that
    door and honours the key, though the API is not that address."""

    def test_a_key_for_this_door_is_accepted(self, site):
        raw, token = _issue(UserFactory(), resource=["http://mcp.t.localhost/mcp"])
        assert _resolve(raw).token.row == token

    def test_the_comparison_is_canonical(self, site):
        """A client names the resource lowercased, without a default port
        or a trailing slash; a domain someone typed may carry any of the
        three. The same door, however spelt."""
        for spelling in ("HTTP://MCP.T.LOCALHOST/mcp", "http://mcp.t.localhost:80/mcp", "http://mcp.t.localhost/mcp/"):
            raw, _ = _issue(UserFactory(), resource=[spelling])
            assert _resolve(raw) is not None, spelling

    def test_one_of_several_is_enough(self, site):
        raw, _ = _issue(UserFactory(), resource=["http://mcp.other.localhost/mcp", "http://mcp.t.localhost/mcp"])
        assert _resolve(raw) is not None

    def test_no_resource_is_the_librarys_rule(self, site):
        """Accepted before our check is asked: the library treats a key
        naming no resource as good anywhere. Our own keys and a by-hand
        probe carry none; pinned so the fact stays visible."""
        from unittest.mock import patch

        raw, _ = _issue(UserFactory())
        with patch("phoxtail.tokens.audience.names_this_server", return_value=False) as ours:
            assert _resolve(raw) is not None
        ours.assert_not_called()

    def test_the_validator_ignores_where_the_request_went(self, site):
        from phoxtail.tokens.audience import names_this_server

        assert names_this_server("http://anything/at/all", ["http://mcp.t.localhost/mcp"]) is True
        assert names_this_server("http://mcp.t.localhost/mcp", ["http://elsewhere.example/mcp"]) is False


class TestWhatTheApiSays:
    def test_whoami_answers_for_an_issued_key(self, site, client):
        raw, _ = _issue(UserFactory(), scope="cms:read")
        response = client.get("/api/whoami/", HTTP_AUTHORIZATION=f"Bearer {raw}", HTTP_HOST=HOST)
        assert response.status_code == 200
        answer = json.loads(response.content)
        assert answer["bundles"] == ["cms:read"]
        assert answer["scopes"] == sorted(bundles.derive()["cms:read"])
        assert answer["unrestricted"] is False

    def test_whoami_names_the_bundles_of_a_phoxtail_key(self, site, client):
        token = AccessTokenFactory(unrestricted=False, scopes=["wagtailcore.publish_page", "cms:read"])
        answer = json.loads(
            client.get("/api/whoami/", HTTP_AUTHORIZATION=f"Bearer {token._raw_token}", HTTP_HOST=HOST).content
        )
        assert answer["bundles"] == ["cms:read"]
        assert "wagtailcore.publish_page" in answer["scopes"]

    def test_a_door_it_covers_opens_and_one_it_does_not_names_the_codename(self, site, client):
        raw, _ = _issue(UserFactory(is_superuser=True), scope="cms:read")
        headers = {"HTTP_AUTHORIZATION": f"Bearer {raw}", "HTTP_HOST": HOST}
        assert client.get("/api/cms/v1/pages/", **headers).status_code == 200
        refused = client.get("/api/users/v1/users/", **headers)
        assert refused.status_code == 403
        assert "phoxtail_users.view_user" in json.loads(refused.content)["detail"]

    def test_an_unannotated_door_says_what_is_missing_on_its_own_side(self, site, client):
        """A key from the authorization server is never unrestricted, so
        the refusal must not tell its holder to get one."""
        raw, _ = _issue(UserFactory(), scope="cms:read")
        response = client.get("/api/ping/", HTTP_AUTHORIZATION=f"Bearer {raw}", HTTP_HOST=HOST)
        assert response.status_code == 403
        detail = json.loads(response.content)["detail"]
        assert "has not named the permission" in detail
        assert "Use an unrestricted token" not in detail
