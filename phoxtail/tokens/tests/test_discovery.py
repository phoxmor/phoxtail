"""The authorization server publishes its card where a stranger can find it.

The MCP server's resource document names this site as the place a client
obtains a credential. That name is all the client has; from it, and nothing
else, it must be able to compute one address and read everything else
there: which doors exist and where each one is.
"""

import json

import pytest
from django.test import override_settings

from phoxtail.tokens.apps import PhoxtailTokensConfig

ISSUER = "http://t.localhost/"


@pytest.fixture
def site(tmp_path, monkeypatch, settings):
    toml = tmp_path / "phoxtail.toml"
    toml.write_text('[project]\nname = "t"\n\n[studio]\napi_url = "http://t.localhost"\n')
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("DOMAIN", raising=False)
    from phoxtail.cli.utils.config import load_config

    load_config.cache_clear()
    settings.ROOT_URLCONF = "phoxtail.tokens.tests.discovery_urls"
    settings.ALLOWED_HOSTS = ["t.localhost"]
    yield
    load_config.cache_clear()


@pytest.fixture
def declared(site):
    """What a project gets: the app's declaration, evaluated inside the
    project the way a real start evaluates it. The app was imported before
    this project existed, so the same function is evaluated again here."""
    from phoxtail.tokens import provider

    assert set(PhoxtailTokensConfig.default_settings["OAUTH2_PROVIDER"]) == set(provider.defaults())
    return provider.defaults()


def _card(client):
    response = client.get("/.well-known/oauth-authorization-server", HTTP_HOST="t.localhost")
    assert response.status_code == 200
    return json.loads(response.content)


@pytest.mark.django_db
class TestTheCardIsWhereAStrangerLooks:
    def test_it_is_at_the_root_and_the_doors_are_under_o(self, client, site, declared):
        """Mounted through the app protocol, so a hatched project that never
        edited its own urls.py still serves it."""
        with override_settings(OAUTH2_PROVIDER=declared):
            card = _card(client)
        assert card["authorization_endpoint"] == "http://t.localhost/o/authorize/"
        assert card["token_endpoint"] == "http://t.localhost/o/token/"
        assert "S256" in card["code_challenge_methods_supported"]

    def test_a_stranger_can_read_how_to_introduce_itself(self, client, site, declared):
        """Both ways, on the card: by request at the registration endpoint,
        and by document — which a client prefers when it sees the flag."""
        with override_settings(OAUTH2_PROVIDER=declared):
            card = _card(client)
        assert card["registration_endpoint"] == "http://t.localhost/o/register/"
        assert card["client_id_metadata_document_supported"] is True

    def test_the_site_does_not_yet_call_itself_a_resource(self, client, site):
        """The library would publish a protected-resource document for the
        site with its placeholder scopes. Whether the API is a declared
        resource, and with what, is not decided; until it is, nothing is
        said."""
        response = client.get("/.well-known/oauth-protected-resource", HTTP_HOST="t.localhost")
        assert response.status_code == 404

    def test_the_card_offers_nothing_the_library_only_tolerates(self, client, site, declared):
        """Left to its defaults the library advertises the implicit and
        password grants and a plain PKCE challenge, kept for deployments
        older than the advice against them. A card is a promise; these are
        not offered."""
        with override_settings(OAUTH2_PROVIDER=declared):
            card = _card(client)
        assert "implicit" not in card["grant_types_supported"]
        assert "password" not in card["grant_types_supported"]
        assert card["code_challenge_methods_supported"] == ["S256"]
        assert card["response_types_supported"] == ["code"]
        assert card["authorization_response_iss_parameter_supported"] is True

    def test_a_public_client_can_read_that_it_may_be_one(self, client, site, declared):
        """A phone or a CLI has no secret to present; it authenticates with
        none and proves itself with PKCE. The library accepts that, and the
        card now says so."""
        with override_settings(OAUTH2_PROVIDER=declared):
            card = _card(client)
        assert "none" in card["token_endpoint_auth_methods_supported"]
        assert "client_secret_basic" in card["token_endpoint_auth_methods_supported"]

    def test_the_issuer_is_the_name_the_mcp_server_advertises(self, client, site, declared):
        """The resource document serialises the site as a root URL with a
        trailing slash, and a client compares that against ``issuer`` as a
        plain string. Left to derive its own name the server would say
        ``http://t.localhost`` — one character short, and the flow would
        stop at the first fetch."""
        assert declared["OIDC_ISS_ENDPOINT"] == ISSUER
        with override_settings(OAUTH2_PROVIDER=declared):
            card = _card(client)
        assert card["issuer"] == ISSUER


class TestTheAppOwnsIt:
    def test_the_server_arrives_with_the_app(self):
        """A hatched project lists phoxtail.tokens; the dependency pulls the
        authorization server into INSTALLED_APPS with nothing edited."""
        from phoxtail.core.wiring import _resolve_dependencies

        installed = _resolve_dependencies(["phoxtail.tokens"])
        assert installed.index("oauth2_provider") < installed.index("phoxtail.tokens")
        assert PhoxtailTokensConfig.url_mount.prefix == ""
        assert PhoxtailTokensConfig.url_mount.i18n is False


class TestTheCheckHoldsTheLine:
    """The defaults are applied to the whole dict at once, so a project that
    writes its own OAUTH2_PROVIDER loses every key in them without noticing.
    The system check is what notices."""

    @staticmethod
    def _shipped():
        return dict(PhoxtailTokensConfig.default_settings["OAUTH2_PROVIDER"])

    def test_the_shipped_defaults_pass(self):
        from phoxtail.tokens.checks import authorization_server_posture

        with override_settings(OAUTH2_PROVIDER=self._shipped()):
            assert authorization_server_posture(None) == []

    def test_a_replaced_dict_fails_on_every_count(self):
        from phoxtail.tokens.checks import authorization_server_posture

        with override_settings(OAUTH2_PROVIDER={"SCOPES": {"read": "Read"}}):
            ids = sorted(e.id for e in authorization_server_posture(None))
        assert ids == (
            ["phoxtail_tokens.E001"]
            + ["phoxtail_tokens.E002"] * 5
            + ["phoxtail_tokens.E004"] * 2
            + ["phoxtail_tokens.E005"]
            + ["phoxtail_tokens.E006"] * 3
        )

    def test_a_displaced_vocabulary_is_caught(self):
        """The library's own backend would hand outsiders its placeholder
        pair, and every bundle a client had stored would validate as
        unknown."""
        from phoxtail.tokens.checks import authorization_server_posture

        shipped = self._shipped()
        shipped["SCOPES_BACKEND_CLASS"] = "oauth2_provider.scopes.SettingsScopes"
        with override_settings(OAUTH2_PROVIDER=shipped):
            assert [e.id for e in authorization_server_posture(None)] == ["phoxtail_tokens.E004"]

    def test_a_retyped_issuer_is_caught(self):
        """The one character the whole flow turns on."""
        from phoxtail.tokens.checks import authorization_server_posture

        shipped = self._shipped()
        shipped["OIDC_ISS_ENDPOINT"] = shipped["OIDC_ISS_ENDPOINT"].rstrip("/")
        with override_settings(OAUTH2_PROVIDER=shipped):
            assert [e.id for e in authorization_server_posture(None)] == ["phoxtail_tokens.E001"]

    def test_one_gate_off_is_one_error(self):
        from phoxtail.tokens.checks import authorization_server_posture

        shipped = self._shipped()
        shipped["COMPLIANT_BCP_RFC9700_PASSWORD_GRANT"] = False
        with override_settings(OAUTH2_PROVIDER=shipped):
            errors = authorization_server_posture(None)
        assert [e.id for e in errors] == ["phoxtail_tokens.E002"]
        assert "PASSWORD_GRANT" in errors[0].msg


@pytest.mark.django_db
class TestACliClientCanComeHome:
    """A CLI listens for its callback on a port it picks at run time, so the
    URI it registered and the one it sends differ by port. Loopback IPs are
    exempt from exact matching by RFC 8252; the name "localhost" only when
    the site opts in — and that is the name such clients use."""

    def _application(self, redirect):
        from oauth2_provider.models import Application

        from .factories import UserFactory

        return Application.objects.create(
            user=UserFactory(),
            client_type=Application.CLIENT_PUBLIC,
            authorization_grant_type=Application.GRANT_AUTHORIZATION_CODE,
            redirect_uris=redirect,
            name="cli",
        )

    def test_any_port_on_localhost_is_the_registered_client(self, site, declared):
        app = self._application("http://localhost:9999/callback")
        with override_settings(OAUTH2_PROVIDER=declared):
            assert app.redirect_uri_allowed("http://localhost:51234/callback")
            assert not app.redirect_uri_allowed("http://localhost:51234/elsewhere")
            assert not app.redirect_uri_allowed("http://example.com:9999/callback")

    def test_without_the_opt_in_the_port_must_match(self, site, declared):
        app = self._application("http://localhost:9999/callback")
        with override_settings(OAUTH2_PROVIDER={**declared, "ALLOW_LOCALHOST_LOOPBACK": False}):
            assert not app.redirect_uri_allowed("http://localhost:51234/callback")
            assert app.redirect_uri_allowed("http://localhost:9999/callback")


class TestTheLifetimes:
    """What the server ships: an hour for the key shown on every call, a
    week for the key that mints keys, and a replayed refresh token revokes
    the family."""

    def test_the_declared_values(self, site, declared):
        assert declared["ACCESS_TOKEN_EXPIRE_SECONDS"] == 3600
        assert declared["REFRESH_TOKEN_EXPIRE_SECONDS"] == 7 * 86400
        assert declared["ROTATE_REFRESH_TOKEN"] is True
        assert declared["REFRESH_TOKEN_REUSE_PROTECTION"] is True
        # Not a minute: the library's grace path returns the previous token's
        # stored value, which hashing at rest leaves blank, and errors.
        assert declared["REFRESH_TOKEN_GRACE_PERIOD_SECONDS"] == 0
        assert declared["COMPLIANT_BCP_RFC9700_TOKEN_STORAGE"] is True

    def test_a_grace_period_is_refused_while_tokens_are_hashed(self):
        """Not a preference: with the storage gate on, the library's grace
        path hands back a blank token and errors. Raising the grace again
        must fail startup, not production."""
        from phoxtail.tokens.checks import authorization_server_posture

        shipped = dict(PhoxtailTokensConfig.default_settings["OAUTH2_PROVIDER"])
        shipped["REFRESH_TOKEN_GRACE_PERIOD_SECONDS"] = 60
        with override_settings(OAUTH2_PROVIDER=shipped):
            assert [e.id for e in authorization_server_posture(None)] == ["phoxtail_tokens.E003"]
        # With the storage gate off the grace path works; that is already its
        # own error, and this one must not contradict it.
        shipped["COMPLIANT_BCP_RFC9700_TOKEN_STORAGE"] = False
        with override_settings(OAUTH2_PROVIDER=shipped):
            assert [e.id for e in authorization_server_posture(None)] == ["phoxtail_tokens.E002"]
