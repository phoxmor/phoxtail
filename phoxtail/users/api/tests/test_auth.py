"""What each users endpoint asks of its caller.

The surface used to be superuser-only, decided once where the router was
mounted. Now every endpoint names the permission its act requires and
``guarded()`` asks both halves about it: whether the person holds it, and
whether their credential covers it.

A superuser is still admitted everywhere, because Django's ``has_perm``
answers True for one. What changed is that they are no longer the *only*
ones — which is the point, and why these tests check a permission rather
than a flag.
"""

from __future__ import annotations

import pytest
from django.contrib.auth.models import Permission

PATHS = ["/users/v1/users/", "/users/v1/genders/"]
READ_PERMS = {"/users/v1/users/": "view_user", "/users/v1/genders/": "view_gender"}


def grant(user, codename: str):
    """Give *user* a permission and hand back an instance that can see it.

    Django caches permissions on the user instance at first lookup, and the
    request is served with the instance the test holds, so a fresh one is the
    documented way to make a just-granted permission visible.
    """
    user.user_permissions.add(Permission.objects.get(codename=codename, content_type__app_label="phoxtail_users"))
    return type(user).objects.get(pk=user.pk)


@pytest.mark.parametrize("path", PATHS)
def test_unauthenticated_request_is_401(db, raw_client, path):
    """No caller at all is a different event from the wrong caller."""
    assert raw_client.get(path).status_code == 401


@pytest.mark.parametrize("path", PATHS)
def test_without_the_permission_is_403(raw_client, regular_user, path):
    response = raw_client.get(path, user=regular_user)
    assert response.status_code == 403


@pytest.mark.parametrize("path", PATHS)
def test_the_refusal_names_the_permission(raw_client, regular_user, path):
    """Naming it is what makes the refusal actionable for whoever reads it.

    "requires a superuser" told the reader what they were not; the codename
    tells an administrator exactly what to grant.
    """
    response = raw_client.get(path, user=regular_user)
    assert READ_PERMS[path] in response.json()["detail"]


@pytest.mark.parametrize("path", PATHS)
def test_holding_the_permission_is_enough(raw_client, regular_user, path):
    """The widening this commit is for: no superuser flag involved."""
    user = grant(regular_user, READ_PERMS[path])
    assert raw_client.get(path, user=user).status_code == 200


def test_a_permission_does_not_carry_to_another_act(raw_client, regular_user):
    """One codename per act, so reading users grants nothing about genders."""
    user = grant(regular_user, "view_user")
    assert raw_client.get("/users/v1/users/", user=user).status_code == 200
    assert raw_client.get("/users/v1/genders/", user=user).status_code == 403


def test_reading_does_not_grant_writing(raw_client, regular_user):
    response = raw_client.post(
        "/users/v1/users/",
        json={"email": "x@example.com", "first_name": "X", "last_name": "Y"},
        user=regular_user,
    )
    assert response.status_code == 403
    assert "add_user" in response.json()["detail"]


def test_superuser_is_still_admitted(client):
    """Unchanged for them: Django answers has_perm True for a superuser."""
    assert client.get("/users/v1/users/").status_code == 200


def test_inactive_superuser_is_403(raw_client, superuser):
    """``has_perm`` is False for an inactive user, superuser or not."""
    superuser.is_active = False
    superuser.save()
    assert raw_client.get("/users/v1/users/", user=superuser).status_code == 403
