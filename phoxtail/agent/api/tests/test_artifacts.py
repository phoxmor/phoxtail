"""Artifact endpoints: full CRUD, permission labels, ETag lifecycle."""

from __future__ import annotations

from phoxtail.agent.models import InferenceProvider, ModelArtifact

PERMISSION = "phoxtail_agent.access_chatbot"


def test_create_and_list(client, provider):
    response = client.post(
        "/agent/v1/artifacts/",
        json={
            "provider_uuid": str(provider.uuid),
            "identifier": "gemini-2.5-pro",
            "display_name": "Gemini 2.5 Pro",
            "sort_order": 3,
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["provider"]["identifier"] == "google-gemini"
    assert data["permission"] is None
    assert data["sort_order"] == 3
    assert response["ETag"].startswith('W/"')

    listing = client.get("/agent/v1/artifacts/")
    assert listing.json()["total"] == 1


def test_create_with_permission(client, provider):
    response = client.post(
        "/agent/v1/artifacts/",
        json={
            "provider_uuid": str(provider.uuid),
            "identifier": "gemini-3.1-pro-preview",
            "display_name": "Gemini 3.1 Pro",
            "permission": PERMISSION,
        },
    )
    assert response.status_code == 201
    assert response.json()["permission"] == PERMISSION


def test_unknown_permission_is_422(client, provider):
    response = client.post(
        "/agent/v1/artifacts/",
        json={
            "provider_uuid": str(provider.uuid),
            "identifier": "x",
            "display_name": "X",
            "permission": "phoxtail_agent.no_such_permission",
        },
    )
    assert response.status_code == 422


def test_unknown_provider_is_404(client):
    response = client.post(
        "/agent/v1/artifacts/",
        json={
            "provider_uuid": "00000000-0000-0000-0000-000000000000",
            "identifier": "x",
            "display_name": "X",
        },
    )
    assert response.status_code == 404


def test_duplicate_identifier_within_provider_is_422(client, provider, artifact):
    response = client.post(
        "/agent/v1/artifacts/",
        json={
            "provider_uuid": str(provider.uuid),
            "identifier": artifact.identifier,
            "display_name": "Duplicate",
        },
    )
    assert response.status_code == 422


def test_provider_filter(client, provider, artifact):
    other = InferenceProvider.objects.create(identifier="anthropic", display_name="Anthropic")
    ModelArtifact.objects.create(provider=other, identifier="claude-opus-5", display_name="Opus 5")

    assert client.get("/agent/v1/artifacts/").json()["total"] == 2
    scoped = client.get(f"/agent/v1/artifacts/?provider_uuid={provider.uuid}").json()
    assert scoped["total"] == 1
    assert scoped["artifacts"][0]["uuid"] == str(artifact.uuid)


def test_search_keeps_sort_order(client, provider, artifact):
    # ``autocomplete()`` returns SearchResults, which drops the queryset's
    # ordering and joins — the search branch must not lose either.
    ModelArtifact.objects.create(
        provider=provider,
        identifier="gemini-2.5-flash",
        display_name="Gemini 2.5 Flash",
        sort_order=-1,
    )
    body = client.get("/agent/v1/artifacts/?search=gemini").json()
    assert body["total"] == 2
    assert [a["sort_order"] for a in body["artifacts"]] == [-1, 0]
    assert body["artifacts"][0]["provider"]["identifier"] == "google-gemini"


def test_update_requires_if_match(client, artifact):
    response = client.patch(f"/agent/v1/artifacts/{artifact.uuid}/", json={"display_name": "Flash"})
    assert response.status_code == 428


def test_sort_order_change_invalidates_etag(client, artifact):
    etag = client.get(f"/agent/v1/artifacts/{artifact.uuid}/")["ETag"]
    client.patch(
        f"/agent/v1/artifacts/{artifact.uuid}/",
        json={"sort_order": 5},
        headers={"If-Match": etag},
    )
    response = client.patch(
        f"/agent/v1/artifacts/{artifact.uuid}/",
        json={"display_name": "Flash"},
        headers={"If-Match": etag},
    )
    assert response.status_code == 412


def test_clear_permission(client, artifact):
    etag = client.get(f"/agent/v1/artifacts/{artifact.uuid}/")["ETag"]
    granted = client.patch(
        f"/agent/v1/artifacts/{artifact.uuid}/",
        json={"permission": PERMISSION},
        headers={"If-Match": etag},
    )
    assert granted.json()["permission"] == PERMISSION

    cleared = client.patch(
        f"/agent/v1/artifacts/{artifact.uuid}/",
        json={"permission": None},
        headers={"If-Match": granted["ETag"]},
    )
    assert cleared.status_code == 200
    assert cleared.json()["permission"] is None


def test_move_to_another_provider(client, artifact):
    other = InferenceProvider.objects.create(identifier="anthropic", display_name="Anthropic")
    etag = client.get(f"/agent/v1/artifacts/{artifact.uuid}/")["ETag"]
    response = client.patch(
        f"/agent/v1/artifacts/{artifact.uuid}/",
        json={"provider_uuid": str(other.uuid)},
        headers={"If-Match": etag},
    )
    assert response.status_code == 200
    assert response.json()["provider"]["identifier"] == "anthropic"


def test_delete(client, artifact):
    response = client.delete(f"/agent/v1/artifacts/{artifact.uuid}/")
    assert response.status_code == 200
    assert not ModelArtifact.objects.filter(pk=artifact.pk).exists()
