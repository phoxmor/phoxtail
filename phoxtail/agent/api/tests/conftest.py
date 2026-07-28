"""Fixtures for agent v1 API tests.

The tests run against the real shared ``phoxtail.api`` NinjaAPI instance
so they exercise the full production wiring: the agent router auto-mounted
at ``/agent/v1/`` and the shared DjangoValidationError → 422 handler.
"""

from __future__ import annotations

import pytest
from ninja.testing import TestClient

from phoxtail.agent.models import InferenceProvider, ModelArtifact


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
        username="agent-admin",
        email="agent-admin@example.com",
        password="irrelevant",
        first_name="Agent",
        last_name="Admin",
    )


@pytest.fixture
def client(raw_client, superuser):
    return AuthedClient(raw_client, superuser)


@pytest.fixture
def provider(db):
    return InferenceProvider.objects.create(
        identifier="google-gemini",
        display_name="Google Gemini",
        model_prefix="google-gla",
        api_key_env_var="GEMINI_API_KEY",
    )


@pytest.fixture
def artifact(provider):
    return ModelArtifact.objects.create(
        provider=provider,
        identifier="gemini-3-flash-preview",
        display_name="Gemini 3 Flash",
        sort_order=0,
    )


@pytest.fixture
def site(db):
    from wagtail.models import Site

    return Site.objects.get(is_default_site=True)
