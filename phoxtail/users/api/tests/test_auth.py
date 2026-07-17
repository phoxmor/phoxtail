"""The superuser gate in front of every users/genders endpoint."""

from __future__ import annotations

import pytest


@pytest.mark.parametrize("path", ["/users/v1/users/", "/users/v1/genders/"])
def test_unauthenticated_request_is_401(db, raw_client, path):
    response = raw_client.get(path)
    assert response.status_code == 401


@pytest.mark.parametrize("path", ["/users/v1/users/", "/users/v1/genders/"])
def test_authenticated_non_superuser_is_403(raw_client, regular_user, path):
    response = raw_client.get(path, user=regular_user)
    assert response.status_code == 403
    assert "superuser" in response.json()["detail"]


def test_inactive_superuser_is_403(raw_client, superuser):
    superuser.is_active = False
    superuser.save()
    response = raw_client.get("/users/v1/users/", user=superuser)
    assert response.status_code == 403


def test_superuser_is_200(client):
    response = client.get("/users/v1/users/")
    assert response.status_code == 200


def test_writes_are_gated_too(raw_client, regular_user):
    response = raw_client.post(
        "/users/v1/users/",
        json={"email": "x@example.com", "first_name": "X", "last_name": "Y"},
        user=regular_user,
    )
    assert response.status_code == 403
