"""A refresh token is spent once; spending it again ends the family."""

import base64
import hashlib
import json
import secrets

import pytest
from django.test import override_settings
from oauth2_provider.models import AccessToken, Application, RefreshToken

from phoxtail.tokens.provider import defaults

from .factories import UserFactory

HOST = "t.localhost"
REDIRECT = "http://localhost:9999/cb"


@pytest.fixture
def site(tmp_path, monkeypatch, settings):
    toml = tmp_path / "phoxtail.toml"
    toml.write_text(f'[project]\nname = "t"\n\n[studio]\napi_url = "http://{HOST}"\n')
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("DOMAIN", raising=False)
    from phoxtail.cli.utils.config import load_config

    load_config.cache_clear()
    settings.ROOT_URLCONF = "phoxtail.tokens.tests.discovery_urls"
    settings.ALLOWED_HOSTS = [HOST]
    with override_settings(OAUTH2_PROVIDER=defaults()):
        yield
    load_config.cache_clear()


def _checksum(raw):
    return hashlib.sha256(raw.encode()).hexdigest()


@pytest.fixture
def first_pair(site, client):
    """Mint the pair a public client gets after consent. The consent screen
    is not exercised here — it needs a browser session — so the grant it
    would leave behind is written directly, challenge included. What runs
    for real is the exchange: PKCE verification, the pair, and everything
    after."""
    from datetime import timedelta

    from django.utils import timezone
    from oauth2_provider.models import Grant

    user = UserFactory()
    app = Application.objects.create(
        user=user,
        client_type=Application.CLIENT_PUBLIC,
        authorization_grant_type=Application.GRANT_AUTHORIZATION_CODE,
        redirect_uris=REDIRECT,
        name="probe",
    )
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    Grant.objects.create(
        user=user,
        application=app,
        code="the-code",
        expires=timezone.now() + timedelta(minutes=1),
        redirect_uri=REDIRECT,
        scope="read",
        code_challenge=challenge,
        code_challenge_method="S256",
    )
    response = client.post(
        "/o/token/",
        {
            "grant_type": "authorization_code",
            "code": "the-code",
            "redirect_uri": REDIRECT,
            "client_id": app.client_id,
            "code_verifier": verifier,
        },
        HTTP_HOST=HOST,
    )
    assert response.status_code == 200, response.content
    return app, json.loads(response.content)


def _refresh(client, app, refresh_token):
    response = client.post(
        "/o/token/",
        {"grant_type": "refresh_token", "refresh_token": refresh_token, "client_id": app.client_id},
        HTTP_HOST=HOST,
    )
    return response.status_code, json.loads(response.content)


@pytest.mark.django_db
class TestTokensAtRest:
    def test_nothing_usable_is_stored(self, first_pair):
        _, pair = first_pair
        access = AccessToken.objects.get(token_checksum=_checksum(pair["access_token"]))
        refresh = RefreshToken.objects.get(token_checksum=_checksum(pair["refresh_token"]))
        assert access.token == "" and refresh.token == ""
        assert pair["expires_in"] == 3600


@pytest.mark.django_db
class TestRotation:
    def test_a_refresh_retires_the_old_and_issues_a_new(self, client, first_pair):
        app, pair = first_pair
        status, second = _refresh(client, app, pair["refresh_token"])
        assert status == 200
        assert second["refresh_token"] != pair["refresh_token"]
        assert second["access_token"] != pair["access_token"]

    def test_a_replayed_refresh_token_ends_the_family(self, client, first_pair):
        """Someone presenting a retired token holds a copy — the thief or the
        real client, and the server cannot know which. Everything descended
        from that grant is revoked, and the person logs in again."""
        app, pair = first_pair
        _, second = _refresh(client, app, pair["refresh_token"])
        status, body = _refresh(client, app, pair["refresh_token"])
        assert (status, body["error"]) == (400, "invalid_grant")
        status, body = _refresh(client, app, second["refresh_token"])
        assert (status, body["error"]) == (400, "invalid_grant")
        assert not AccessToken.objects.filter(token_checksum=_checksum(second["access_token"])).exists()
