"""Fixtures for users v1 API tests.

The tests run against the real shared ``phoxtail.api`` NinjaAPI instance
so they exercise the full production wiring: the users router mounted at
``/users/v1/`` behind the superuser ``Authorize`` stack, and the shared
DjangoValidationError → 422 exception handler.
"""

from __future__ import annotations

import pytest
from ninja.testing import TestClient

from phoxtail.users.models import Gender


class AuthedClient:
    """TestClient wrapper that authenticates every request as ``user``."""

    def __init__(self, client: TestClient, user):
        self._client = client
        self._user = user

    def __getattr__(self, method):
        def call(*args, **kwargs):
            kwargs.setdefault("user", self._user)
            # allauth's adapter helpers read request.session; the mocked
            # TestClient request has none (SessionMiddleware adds it in
            # production), so provide a dict-backed stand-in.
            kwargs.setdefault("session", {})
            return getattr(self._client, method)(*args, **kwargs)

        return call


@pytest.fixture(scope="session")
def raw_client():
    from phoxtail.api import api

    return TestClient(api)


@pytest.fixture
def superuser(db, django_user_model):
    return django_user_model.objects.create_superuser(
        username="api-admin",
        email="api-admin@example.com",
        password="irrelevant",
        first_name="API",
        last_name="Admin",
    )


@pytest.fixture
def regular_user(db, django_user_model):
    return django_user_model.objects.create_user(
        username="api-member",
        email="api-member@example.com",
        password="irrelevant",
        first_name="API",
        last_name="Member",
    )


@pytest.fixture
def client(raw_client, superuser):
    return AuthedClient(raw_client, superuser)


@pytest.fixture
def gender(db):
    return Gender.objects.create(name="Female", symbol="F")
