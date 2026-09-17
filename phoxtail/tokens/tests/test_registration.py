"""A client the site has never met introduces itself, and is granted nothing.

By request: it posts its name and where it will listen, and receives a
client id. By document: its id is an https URL the site fetches. Either
way the row it leaves behind is public, sends every person to the
consent screen, and cannot mark itself as needing no consent — the one
field that would bypass the screen is never read from a client.
"""

import json

import pytest
from django.conf import settings
from django.test import override_settings
from oauth2_provider.models import Application

from .factories import UserFactory

HOST = "t.localhost"
REDIRECT = "http://localhost:9999/cb"
DOCUMENT = "https://clients.example/agent/metadata.json"
CHALLENGE = "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"

pytestmark = [
    pytest.mark.django_db,
    pytest.mark.skipif(
        "phoxtail.agent" not in settings.INSTALLED_APPS,
        reason="renders the consent screen, which needs the project's app set",
    ),
]

# What an MCP client sends when it registers by request.
INTRODUCTION = {
    "client_name": "A stranger",
    "redirect_uris": [REDIRECT],
    "token_endpoint_auth_method": "none",
    "grant_types": ["authorization_code", "refresh_token"],
    "response_types": ["code"],
}


@pytest.fixture
def site(tmp_path, monkeypatch, settings):
    toml = tmp_path / "phoxtail.toml"
    toml.write_text(f'[project]\nname = "t"\n\n[studio]\napi_url = "http://{HOST}"\n')
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("DOMAIN", raising=False)
    from phoxtail.cli.utils.config import load_config
    from phoxtail.tokens.provider import defaults

    load_config.cache_clear()
    settings.ROOT_URLCONF = "phoxtail.tokens.tests.discovery_urls"
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


def _register(client, body):
    return client.post("/o/register/", json.dumps(body), content_type="application/json", HTTP_HOST=HOST)


class TestByRequest:
    def test_a_stranger_receives_a_name_and_no_secret(self, client, site):
        response = _register(client, INTRODUCTION)
        assert response.status_code == 201, response.content
        answer = json.loads(response.content)
        assert answer["client_id"]
        assert "client_secret" not in answer
        assert answer["token_endpoint_auth_method"] == "none"
        row = Application.objects.get(client_id=answer["client_id"])
        assert row.registration_source == Application.RegistrationSource.DCR
        assert row.client_type == Application.CLIENT_PUBLIC
        assert row.redirect_uris == REDIRECT

    def test_it_cannot_excuse_itself_from_consent(self, client, site):
        """The one field that would bypass the screen, asked for and
        ignored: the row is created as every row is."""
        answer = json.loads(_register(client, {**INTRODUCTION, "skip_authorization": True}).content)
        assert Application.objects.get(client_id=answer["client_id"]).skip_authorization is False

    def test_it_can_read_back_what_it_said(self, client, site):
        answer = json.loads(_register(client, INTRODUCTION).content)
        response = client.get(
            answer["registration_client_uri"].replace(f"http://{HOST}", ""),
            HTTP_AUTHORIZATION=f"Bearer {answer['registration_access_token']}",
            HTTP_HOST=HOST,
        )
        assert response.status_code == 200
        assert json.loads(response.content)["client_name"] == "A stranger"

    def test_a_person_still_decides(self, client, site):
        """Registered is not allowed: the new client's first request lands
        on the consent screen like any other."""
        answer = json.loads(_register(client, INTRODUCTION).content)
        client.force_login(UserFactory())
        response = client.get(
            "/o/authorize/",
            {
                "response_type": "code",
                "client_id": answer["client_id"],
                "redirect_uri": REDIRECT,
                "scope": "cms:read",
                "code_challenge": CHALLENGE,
                "code_challenge_method": "S256",
            },
            HTTP_HOST=HOST,
        )
        assert response.status_code == 200
        assert "Allow access?" in response.content.decode()


class _Document:
    """A fetcher standing in for the library's: the document a client
    would publish at its own URL, returned without a network."""

    def fetch(self, client_id):
        return {
            "client_id": client_id,
            "client_name": "Self-described",
            "redirect_uris": [REDIRECT],
            "token_endpoint_auth_method": "none",
            "grant_types": ["authorization_code", "refresh_token"],
        }, 3600


def _authorize_as(client, client_id):
    return client.get(
        "/o/authorize/",
        {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": REDIRECT,
            "scope": "cms:read",
            "code_challenge": CHALLENGE,
            "code_challenge_method": "S256",
        },
        HTTP_HOST=HOST,
    )


class TestByDocument:
    def test_a_url_for_a_name_becomes_a_public_client_shown_by_host(self, client, site, settings):
        client.force_login(UserFactory())
        with override_settings(
            OAUTH2_PROVIDER={**settings.OAUTH2_PROVIDER, "CIMD_METADATA_FETCHER": f"{__name__}._Document"}
        ):
            response = _authorize_as(client, DOCUMENT)
        assert response.status_code == 200
        body = response.content.decode()
        assert "clients.example" in body
        assert "Self-described" not in body
        row = Application.objects.get(client_id=DOCUMENT)
        assert row.registration_source == Application.RegistrationSource.CIMD
        assert row.client_type == Application.CLIENT_PUBLIC
        assert row.skip_authorization is False

    def test_a_document_must_be_served_over_https(self, client, site, settings):
        """The site fetches a client-controlled URL on the pre-auth path.
        Anything but https is not a document id at all: the library never
        reaches the fetcher, and the client is simply unknown."""
        from unittest.mock import patch

        client.force_login(UserFactory())
        with (
            override_settings(
                OAUTH2_PROVIDER={**settings.OAUTH2_PROVIDER, "CIMD_METADATA_FETCHER": f"{__name__}._Document"}
            ),
            patch.object(_Document, "fetch") as fetch,
        ):
            response = _authorize_as(client, "http://clients.example/agent/metadata.json")
        fetch.assert_not_called()
        assert response.status_code == 400
        assert not Application.objects.filter(client_id__startswith="http://").exists()
