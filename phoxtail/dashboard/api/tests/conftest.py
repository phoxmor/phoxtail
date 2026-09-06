"""Fixtures for dashboard v1 API tests.

Run against the real shared ``phoxtail.api`` instance so the tests exercise
the production wiring — the dashboard router auto-mounted at
``/dashboard/v1/`` from ``PhoxtailDashboardConfig.api_version_router``.
"""

from __future__ import annotations

import pytest
from ninja.testing import TestClient
from wagtail.models import Locale, Site


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
def client(raw_client, db, django_user_model):
    user = django_user_model.objects.create_superuser(email="menus@example.com", password="pw")
    return AuthedClient(raw_client, user)


@pytest.fixture
def site(db):
    return Site.objects.get(is_default_site=True)


@pytest.fixture
def locale(db):
    return Locale.get_default()


@pytest.fixture
def greek(db):
    return Locale.objects.create(language_code="el")
