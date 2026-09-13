"""Fixtures for cms v1 API tests.

Run against the real shared ``phoxtail.api`` instance, so the tests exercise
the production wiring: the cms router found at ``/cms/v1/`` because the app
ships ``phoxtail/cms/api/`` declaring ``versions``.
"""

from __future__ import annotations

import pytest
from ninja.testing import TestClient


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
