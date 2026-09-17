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
from oauth2_provider.models import Application

from phoxtail.core.authorization import AuthorizationContext
from phoxtail.tokens import bundles
from phoxtail.tokens.constants import PHOXTAIL_TOKEN_PREFIX
from phoxtail.tokens.ninja import PhoxtailTokenAuth
from phoxtail.tokens.services.admin.operations.create import _generate_raw_token

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


def _issue(user, scope="cms:read", **fields):
    """A key as the authorization server leaves it after a consent: the row
    with its digest, the raw value known only to the client. Written
    directly; the flow that mints one is pinned elsewhere."""
    from oauth2_provider.models import get_access_token_model, set_token_value
    from oauth2_provider.settings import oauth2_settings

    app = Application.objects.create(
        user=user,
        client_type=Application.CLIENT_PUBLIC,
        authorization_grant_type=Application.GRANT_AUTHORIZATION_CODE,
        redirect_uris="http://localhost:9999/cb",
        name="probe",
    )
    raw = "abcdefghij0123456789ABCDEFGHIJ"
    fields.setdefault("expires", timezone.now() + timedelta(seconds=oauth2_settings.ACCESS_TOKEN_EXPIRE_SECONDS))
    token = get_access_token_model()(user=user, application=app, scope=scope, **fields)
    set_token_value(token, raw)
    token.save()
    return raw, token


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

    def test_a_key_bound_to_another_resource_is_refused(self, site):
        """A key minted for the MCP server names it as its resource, and
        the library refuses to spend it anywhere else — the API included,
        until the API can say it stands behind that server. Pinned as the
        behaviour it is today; the lesson that changes it changes this."""
        raw, _ = _issue(UserFactory(), resource=["http://mcp.t.localhost/mcp"])
        assert _resolve(raw) is None


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
