"""Every rule the library can enforce is on, and the one that is not says why.

The library ships each RFC 9700 gate off, waiting for a major version;
a site with no past has nothing to wait for. These pin that every gate
the library defines is either refused from the first day or kept off
for a written reason, so a gate added by a future release fails here
until it is decided; that the last behaviour gate refuses a key in the
query string; and that the rule the kept gate could not express —
plaintext only to loopback — holds in the validator.
"""

import pytest
from django.conf import settings
from django.core import checks
from django.test import override_settings
from oauth2_provider import checks as library_checks
from oauth2_provider.models import Application

from phoxtail.tokens.provider import KEPT_FOR_LOOPBACK, REFUSED_FROM_THE_FIRST_DAY, defaults

from .conftest import issue_key
from .factories import UserFactory

HOST = "t.localhost"
CHALLENGE = "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"

pytestmark = [
    pytest.mark.django_db,
    pytest.mark.skipif(
        "phoxtail.agent" not in settings.INSTALLED_APPS,
        reason="spends a key at the API and renders the consent screen",
    ),
]


@pytest.fixture
def site(tmp_path, monkeypatch, settings):
    toml = tmp_path / "phoxtail.toml"
    toml.write_text(f'[project]\nname = "t"\n\n[studio]\napi_url = "http://{HOST}"\n')
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("DOMAIN", raising=False)
    from phoxtail.cli.utils.config import load_config

    load_config.cache_clear()
    settings.ROOT_URLCONF = "phoxtail.tokens.tests.site_urls"
    settings.ALLOWED_HOSTS = [HOST]
    settings.SESSION_ENGINE = "django.contrib.sessions.backends.signed_cookies"
    settings.MIDDLEWARE = [
        "django.contrib.sessions.middleware.SessionMiddleware",
        "django.contrib.auth.middleware.AuthenticationMiddleware",
        *settings.MIDDLEWARE,
    ]
    with override_settings(OAUTH2_PROVIDER=defaults()):
        yield
    load_config.cache_clear()


def _library_gates() -> set[str]:
    """Every gate the library defines, read off its own check registry."""
    behaviour = {name for name, _behaviour, _id in library_checks._BCP_GATES}
    config = {name for name, *_rest in library_checks._BCP_CONFIG_GATES}
    return behaviour | config


class TestEveryGateIsDecided:
    def test_each_gate_is_refused_or_kept_and_nothing_is_undecided(self):
        decided = set(REFUSED_FROM_THE_FIRST_DAY) | {KEPT_FOR_LOOPBACK}
        assert decided == _library_gates()

    def test_the_shipped_defaults_turn_the_refused_on_and_the_kept_off(self):
        shipped = defaults()
        assert all(shipped[gate] is True for gate in REFUSED_FROM_THE_FIRST_DAY)
        assert KEPT_FOR_LOOPBACK not in shipped

    def test_the_deploy_check_has_one_known_warning_and_no_other(self, site):
        """The library's own check, run as ``--deploy`` runs it: the one
        warning is the plaintext scheme, kept for loopback; nothing else."""
        messages = checks.run_checks(tags=[checks.Tags.security], include_deployment_checks=True)
        ours = [m for m in messages if m.id.startswith("oauth2_provider.")]
        assert [m.id for m in ours] == ["oauth2_provider.W008"]


class TestTheKeptGate:
    """Against what the app declared, as the posture check compares."""

    @staticmethod
    def _shipped():
        from phoxtail.tokens.apps import PhoxtailTokensConfig

        return dict(PhoxtailTokensConfig.default_settings["OAUTH2_PROVIDER"])

    def test_turning_it_on_is_an_error(self):
        from phoxtail.tokens.checks import authorization_server_posture

        with override_settings(OAUTH2_PROVIDER={**self._shipped(), KEPT_FOR_LOOPBACK: True}):
            assert [e.id for e in authorization_server_posture(None)] == ["phoxtail_tokens.E007"]

    def test_dropping_plaintext_is_an_error(self):
        from phoxtail.tokens.checks import authorization_server_posture

        with override_settings(OAUTH2_PROVIDER={**self._shipped(), "ALLOWED_REDIRECT_URI_SCHEMES": ["https"]}):
            assert [e.id for e in authorization_server_posture(None)] == ["phoxtail_tokens.E007"]


class TestAKeyTravelsInTheHeader:
    def test_a_key_in_the_query_string_is_refused(self, site, client):
        """Phoxtail's own reader never looked in the query string; the
        library's gate is what refuses an issued key sent that way."""
        raw, _ = issue_key(UserFactory())
        assert client.get("/api/whoami/", HTTP_AUTHORIZATION=f"Bearer {raw}", HTTP_HOST=HOST).status_code == 200
        assert client.get("/api/whoami/", {"access_token": raw}, HTTP_HOST=HOST).status_code == 401


def _public_client(user, *redirects):
    return Application.objects.create(
        user=user,
        client_type=Application.CLIENT_PUBLIC,
        authorization_grant_type=Application.GRANT_AUTHORIZATION_CODE,
        redirect_uris=" ".join(redirects),
        name="probe",
    )


def _authorize(client, app, redirect):
    return client.get(
        "/o/authorize/",
        {
            "response_type": "code",
            "client_id": app.client_id,
            "redirect_uri": redirect,
            "scope": "cms:read",
            "code_challenge": CHALLENGE,
            "code_challenge_method": "S256",
        },
        HTTP_HOST=HOST,
    )


class TestPlaintextOnlyToLoopback:
    def test_a_program_on_this_machine_may_use_it(self, site, client):
        person = UserFactory()
        client.force_login(person)
        app = _public_client(person, "http://localhost:9999/cb", "http://127.0.0.1:9999/cb")
        for redirect in ("http://localhost:9999/cb", "http://127.0.0.1:9999/cb"):
            assert _authorize(client, app, redirect).status_code == 200, redirect

    def test_any_other_host_may_not_whatever_it_registered(self, site, client):
        """The library would allow it — the scheme is allowed site-wide and
        the URI is registered — so the refusal is phoxtail's rule."""
        person = UserFactory()
        client.force_login(person)
        app = _public_client(person, "http://elsewhere.example/cb")
        response = _authorize(client, app, "http://elsewhere.example/cb")
        assert response.status_code == 400
        assert "invalid_request" in response.content.decode()

    def test_the_same_host_over_https_is_fine(self, site, client):
        person = UserFactory()
        client.force_login(person)
        app = _public_client(person, "https://elsewhere.example/cb")
        assert _authorize(client, app, "https://elsewhere.example/cb").status_code == 200
