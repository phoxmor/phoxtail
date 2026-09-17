"""The consent screen names what a person can check, in phoxtail's chrome.

A client's name is its own to choose. What can be verified is where the
client is — the host of the URL it identifies by, when it has one — and
where the browser is about to be sent. The bundles it asks for are shown
by their descriptions, and a request for a scope that is not a bundle
never reaches the screen.
"""

from urllib.parse import parse_qs, urlsplit

import pytest
from django.test import override_settings
from oauth2_provider.models import Application

from .factories import UserFactory

HOST = "t.localhost"
REDIRECT = "http://localhost:9999/cb"
CHALLENGE = "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"


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
    # The screen is reached by a person in a browser, so the request needs
    # a session and a user on it. The suite installs no session store;
    # the signed-cookie engine needs none.
    settings.SESSION_ENGINE = "django.contrib.sessions.backends.signed_cookies"
    settings.MIDDLEWARE = [
        "django.contrib.sessions.middleware.SessionMiddleware",
        "django.contrib.auth.middleware.AuthenticationMiddleware",
        *settings.MIDDLEWARE,
    ]
    with override_settings(OAUTH2_PROVIDER=defaults()):
        yield
    load_config.cache_clear()


@pytest.fixture
def person(site, client):
    user = UserFactory()
    client.force_login(user)
    return user


def _application(user, **fields):
    return Application.objects.create(
        user=user,
        client_type=Application.CLIENT_PUBLIC,
        authorization_grant_type=Application.GRANT_AUTHORIZATION_CODE,
        name="A name the client chose",
        **{"redirect_uris": REDIRECT, **fields},
    )


def _authorize(client, app, scope="cms:read", redirect=REDIRECT):
    params = {
        "response_type": "code",
        "client_id": app.client_id,
        "redirect_uri": redirect,
        "code_challenge": CHALLENGE,
        "code_challenge_method": "S256",
        "state": "xyz",
    }
    if scope is not None:
        params["scope"] = scope
    return client.get("/o/authorize/", params, HTTP_HOST=HOST)


@pytest.mark.django_db
class TestWhatTheScreenSays:
    def test_bundles_are_shown_by_description(self, client, person):
        app = _application(person)
        response = _authorize(client, app, scope="cms:read media:write")
        assert response.status_code == 200
        body = response.content.decode()
        assert "Read Phoxtail CMS" in body
        assert "Read and change Phoxtail Media" in body

    def test_a_client_named_by_url_is_shown_by_its_host(self, client, person):
        app = _application(
            person,
            client_id="https://clients.example/agent/metadata.json",
            registration_source=Application.RegistrationSource.CIMD,
        )
        body = _authorize(client, app).content.decode()
        assert "clients.example" in body
        assert "A name the client chose" not in body

    def test_a_client_without_a_url_is_shown_by_its_name(self, client, person):
        body = _authorize(client, _application(person)).content.decode()
        assert "A name the client chose" in body

    def test_the_redirect_host_is_named_and_loopback_is_explained(self, client, person):
        body = _authorize(client, _application(person)).content.decode()
        assert "<strong>localhost</strong>" in body
        assert "this computer" in body

    def test_a_remote_redirect_gets_no_loopback_note(self, client, person):
        app = _application(person, redirect_uris="https://client.example/callback")
        body = _authorize(client, app, redirect="https://client.example/callback").content.decode()
        assert "<strong>client.example</strong>" in body
        assert "this computer" not in body


@pytest.mark.django_db
class TestWhatMayBeAsked:
    def test_the_placeholder_is_no_longer_a_scope(self, client, person):
        """The library's ``read`` validated yesterday; today only bundles do,
        and the refusal goes back to the client as ``invalid_scope``."""
        response = _authorize(client, _application(person), scope="read")
        assert response.status_code == 302
        assert parse_qs(urlsplit(response["Location"]).query)["error"] == ["invalid_scope"]

    def test_a_codename_is_not_a_scope_either(self, client, person):
        response = _authorize(client, _application(person), scope="wagtailcore.view_page")
        assert response.status_code == 302
        assert "error=invalid_scope" in response["Location"]

    def test_asking_for_nothing_is_refused_not_shown(self, client, person):
        """With no defaults the library would let an empty request through
        to a screen whose form then refuses to submit; the standard's other
        answer is an error the client understands."""
        for scope in (None, "", " "):
            response = _authorize(client, _application(person), scope=scope)
            assert response.status_code == 302, scope
            assert "error=invalid_scope" in response["Location"], scope

    def test_allowing_delivers_a_code_carrying_the_bundle(self, client, person):
        from oauth2_provider.models import Grant

        app = _application(person)
        page = _authorize(client, app, scope="cms:read")
        form = page.context["form"]
        response = client.post(
            "/o/authorize/",
            {**{name: form[name].value() or "" for name in form.fields}, "allow": "yes"},
            HTTP_HOST=HOST,
        )
        assert response.status_code == 302
        code = parse_qs(urlsplit(response["Location"]).query)["code"][0]
        assert Grant.objects.get(code=code).scope == "cms:read"
