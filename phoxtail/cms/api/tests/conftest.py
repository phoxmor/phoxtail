"""Fixtures for cms v1 API tests.

Run against the real shared ``phoxtail.api`` instance, so the tests exercise
the production wiring: the cms router found at ``/cms/v1/`` because the app
ships ``phoxtail/cms/api/`` declaring ``versions``.

``grant`` takes an app label as well as a codename, because cms spans two:
pages, collections, locales and sites are Wagtail's own models under
``wagtailcore``, while the per-site settings are this app's.
"""

from __future__ import annotations

import pytest
from django.contrib.auth.models import Permission
from ninja.testing import TestClient


class AuthedClient:
    """TestClient wrapper that authenticates every request as ``user``."""

    def __init__(self, client: TestClient, user):
        self._client = client
        self._user = user

    def __getattr__(self, method):
        def call(*args, **kwargs):
            kwargs.setdefault("user", self._user)
            return getattr(self._client, method)(*args, **kwargs)

        return call


@pytest.fixture(scope="session")
def raw_client():
    from phoxtail.api import api

    return TestClient(api)


@pytest.fixture
def regular_user(db, django_user_model):
    return django_user_model.objects.create_user(
        username="cms-member",
        email="cms-member@example.invalid",
        password="irrelevant",
    )


@pytest.fixture
def scoped_token():
    """Mint a real narrowed token and hand back its Bearer header.

    Every other way of authenticating a test here goes through the session
    backend, where ``token`` is ``None`` and the credential half of the
    question is answered "no ceiling" before it is really asked. That makes a
    session test blind to the one property scopes exist for: whether a
    *narrowed* credential can reach this endpoint at all.

    It is a blind spot with teeth. An endpoint that declares nothing keeps the
    API-wide default, which refuses a scoped token — so a door can be shut to
    every narrowed credential in the project and still pass a full suite of
    session-authenticated tests.
    """
    from phoxtail.tokens.tests.factories import AccessTokenFactory

    def _mint(user, *codenames: str) -> dict[str, str]:
        token = AccessTokenFactory(user=user, unrestricted=False, scopes=list(codenames))
        return {"Authorization": f"Bearer {token._raw_token}"}

    return _mint


@pytest.fixture
def superuser(db, django_user_model):
    return django_user_model.objects.create_superuser(
        username="cms-admin",
        email="cms-admin@example.invalid",
        password="irrelevant",
    )


@pytest.fixture
def client(raw_client, superuser):
    return AuthedClient(raw_client, superuser)


@pytest.fixture
def grant():
    """Give a user one permission and hand back a fresh instance.

    Django caches permissions on the user object at first lookup, and the
    request is served with the instance the test holds, so a re-fetch is the
    documented way to make a just-granted permission visible.
    """

    def _grant(user, app_label: str, codename: str):
        user.user_permissions.add(Permission.objects.get(content_type__app_label=app_label, codename=codename))
        return type(user).objects.get(pk=user.pk)

    return _grant


@pytest.fixture
def site(db):
    """The default Site, created by Wagtail's own migrations."""
    from wagtail.models import Site

    return Site.objects.get(is_default_site=True)
