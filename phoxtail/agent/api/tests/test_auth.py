"""What each agent endpoint asks of its caller.

Providers, artifacts and settings asked for nothing beyond being
authenticated: any account with a session or an unrestricted token could add
an inference provider, or point a site's default model at one. Each now names
the permission its act needs and ``guarded()`` asks both halves about it.

Chat is deliberately untouched — see the bottom of this file.

One set per codename rather than per endpoint. Whether an endpoint was missed
is a different question, answered by ``test_tool_scopes.py`` reading the
annotations; what these check is that the codename chosen for an act is the
right one and grants nothing next to it.
"""

from __future__ import annotations

import pytest
from django.contrib.auth.models import Permission

# One readable collection per resource, and the codename that opens it.
READS = {
    "/agent/v1/providers/": "view_inferenceprovider",
    "/agent/v1/artifacts/": "view_modelartifact",
}


def grant(user, codename: str):
    """Give *user* a permission and hand back an instance that can see it.

    Django caches permissions on the user instance at first lookup, and the
    request is served with the instance the test holds, so a fresh one is the
    documented way to make a just-granted permission visible.
    """
    user.user_permissions.add(Permission.objects.get(codename=codename, content_type__app_label="phoxtail_agent"))
    return type(user).objects.get(pk=user.pk)


def test_unauthenticated_request_is_401(db, raw_client):
    """No caller at all is a different event from the wrong caller."""
    assert raw_client.get("/agent/v1/providers/").status_code == 401


@pytest.mark.parametrize("path,codename", sorted(READS.items()))
def test_reading_without_the_permission_is_403(raw_client, regular_user, path, codename):
    response = raw_client.get(path, user=regular_user)
    assert response.status_code == 403
    assert codename in response.json()["detail"]


@pytest.mark.parametrize("path,codename", sorted(READS.items()))
def test_reading_with_the_permission_is_allowed(raw_client, regular_user, path, codename):
    """The widening this commit is for: no superuser flag involved."""
    user = grant(regular_user, codename)
    assert raw_client.get(path, user=user).status_code == 200


def test_a_resource_permission_does_not_reach_the_other(raw_client, regular_user):
    """Providers and artifacts are separate models and separate grants."""
    user = grant(regular_user, "view_inferenceprovider")
    assert raw_client.get("/agent/v1/providers/", user=user).status_code == 200
    assert raw_client.get("/agent/v1/artifacts/", user=user).status_code == 403


def test_reading_providers_does_not_grant_creating_one(raw_client, regular_user):
    user = grant(regular_user, "view_inferenceprovider")
    response = raw_client.post(
        "/agent/v1/providers/",
        json={
            "identifier": "anthropic",
            "display_name": "Anthropic",
            "model_prefix": "anthropic",
            "api_key_env_var": "ANTHROPIC_API_KEY",
        },
        user=user,
    )
    assert response.status_code == 403
    assert "add_inferenceprovider" in response.json()["detail"]


def test_changing_an_artifact_does_not_grant_deleting_it(raw_client, regular_user, artifact):
    user = grant(regular_user, "change_modelartifact")
    response = raw_client.delete(f"/agent/v1/artifacts/{artifact.uuid}/", user=user)
    assert response.status_code == 403
    assert "delete_modelartifact" in response.json()["detail"]


def test_reading_settings_does_not_grant_changing_them(raw_client, regular_user, site, artifact):
    user = grant(regular_user, "view_agentsitesetting")
    assert raw_client.get(f"/agent/v1/settings/{site.id}/", user=user).status_code == 200
    response = raw_client.patch(
        f"/agent/v1/settings/{site.id}/",
        json={"default_artifact_uuid": str(artifact.uuid)},
        headers={"If-Match": "*"},
        user=user,
    )
    assert response.status_code == 403
    assert "change_agentsitesetting" in response.json()["detail"]


def test_superuser_is_still_admitted(client):
    """Unchanged for them: Django answers has_perm True for a superuser."""
    assert client.get("/agent/v1/providers/").status_code == 200


def test_chat_refuses_a_token_and_stays_session_only(db, raw_client):
    """Chat is the one part of this domain no annotation may reach.

    Its two endpoints are browser-only SSE, mounted with their own
    ``PhoxtailSessionAuth()``, and they already ask for ``access_chatbot``
    where the conversation is known. ninja's operation-level ``auth``
    *replaces* the router's, so a ``guarded()`` here would not add a check —
    it would swap a session-only door for one that also admits bearer tokens,
    widening the endpoint while looking like a tightening.

    Asked of the running stack rather than of the decorators. ninja resolves
    a sub-router's ``auth`` somewhere the operation object does not show, so
    reading the annotations here answers a different question than the one
    that matters, and answers it wrongly.
    """
    from phoxtail.tokens.tests.factories import AccessTokenFactory, UserFactory

    user = UserFactory()
    token = AccessTokenFactory(user=user)
    path = "/agent/v1/conversations/00000000-0000-0000-0000-000000000000/"

    # An unrestricted token — the widest credential there is — reaches every
    # other endpoint in this domain and must not reach this one.
    assert raw_client.get(path, headers={"Authorization": f"Bearer {token._raw_token}"}).status_code == 401
    # And no credential at all is refused the same way, not let through.
    assert raw_client.get(path).status_code == 401
