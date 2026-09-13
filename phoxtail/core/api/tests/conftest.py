"""Fixtures for core v1 API tests.

Run against the real shared ``phoxtail.api`` instance, so the tests exercise
the production wiring: the core router found at ``/core/v1/`` because the app
ships ``phoxtail/core/api/`` declaring ``versions``, with each endpoint behind
its own ``guarded()``.
"""

from __future__ import annotations

import pytest
from ninja.testing import TestClient

from phoxtail.core.models import InternalLink


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
        username="core-admin",
        email="core-admin@example.invalid",
        password="irrelevant",
    )


@pytest.fixture
def regular_user(db, django_user_model):
    return django_user_model.objects.create_user(
        username="core-member",
        email="core-member@example.invalid",
        password="irrelevant",
    )


@pytest.fixture
def client(raw_client, superuser):
    return AuthedClient(raw_client, superuser)


@pytest.fixture
def link(db):
    return InternalLink.objects.create(label="My Subscriptions", url_name="dashboard:index")
