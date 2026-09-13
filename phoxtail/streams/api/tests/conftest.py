"""Fixtures for streams v1 API tests.

Run against the real shared ``phoxtail.api`` instance, so the tests exercise
the production wiring: the streams router found at ``/streams/v1/`` because
the app ships ``phoxtail/streams/api/`` declaring ``versions``, with each
endpoint behind its own ``guarded()``.
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
def superuser(db, django_user_model):
    return django_user_model.objects.create_superuser(
        username="streams-admin",
        email="streams-admin@example.invalid",
        password="irrelevant",
    )


@pytest.fixture
def regular_user(db, django_user_model):
    return django_user_model.objects.create_user(
        username="streams-member",
        email="streams-member@example.invalid",
        password="irrelevant",
    )


@pytest.fixture
def client(raw_client, superuser):
    return AuthedClient(raw_client, superuser)


@pytest.fixture
def grant():
    """Give a user one streams permission and hand back a fresh instance.

    Django caches permissions on the user object at first lookup, and the
    request is served with the instance the test holds, so a re-fetch is the
    documented way to make a just-granted permission visible.
    """

    def _grant(user, codename: str):
        user.user_permissions.add(Permission.objects.get(content_type__app_label="phoxtail_streams", codename=codename))
        return type(user).objects.get(pk=user.pk)

    return _grant


@pytest.fixture
def block(db):
    from phoxtail.streams.tests.factories import BlockFactory

    return BlockFactory()


@pytest.fixture
def category(db):
    from phoxtail.streams.models import BlockCategory

    return BlockCategory.objects.create(name="Heroes", slug="heroes")
