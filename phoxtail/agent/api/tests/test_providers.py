"""Provider endpoints: full CRUD with ETag lifecycle."""

from __future__ import annotations

from phoxtail.agent.models import InferenceProvider, ModelArtifact


def test_create_and_list(client):
    response = client.post(
        "/agent/v1/providers/",
        json={
            "identifier": "anthropic",
            "display_name": "Anthropic",
            "model_prefix": "anthropic",
            "api_key_env_var": "ANTHROPIC_API_KEY",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert "id" not in data
    assert data["model_prefix"] == "anthropic"
    assert data["artifact_count"] == 0
    assert response["ETag"].startswith('W/"')

    listing = client.get("/agent/v1/providers/")
    assert listing.status_code == 200
    body = listing.json()
    assert body["total"] == 1
    assert body["providers"][0]["uuid"] == data["uuid"]


def test_duplicate_identifier_is_422(client, provider):
    response = client.post(
        "/agent/v1/providers/",
        json={"identifier": provider.identifier, "display_name": "Copy"},
    )
    assert response.status_code == 422


def test_is_active_filter(client, provider):
    InferenceProvider.objects.create(identifier="retired", display_name="Retired", is_active=False)
    assert client.get("/agent/v1/providers/?is_active=true").json()["total"] == 1
    assert client.get("/agent/v1/providers/?is_active=false").json()["total"] == 1


def test_get_sets_etag(client, provider):
    response = client.get(f"/agent/v1/providers/{provider.uuid}/")
    assert response.status_code == 200
    assert response["ETag"].startswith('W/"')
    assert response.json()["api_key_env_var"] == "GEMINI_API_KEY"


def test_update_requires_if_match(client, provider):
    response = client.patch(f"/agent/v1/providers/{provider.uuid}/", json={"display_name": "Gemini"})
    assert response.status_code == 428


def test_update_rejects_stale_etag(client, provider):
    etag = client.get(f"/agent/v1/providers/{provider.uuid}/")["ETag"]
    client.patch(
        f"/agent/v1/providers/{provider.uuid}/",
        json={"display_name": "First write"},
        headers={"If-Match": etag},
    )
    response = client.patch(
        f"/agent/v1/providers/{provider.uuid}/",
        json={"display_name": "Second write"},
        headers={"If-Match": etag},
    )
    assert response.status_code == 412


def test_update_applies_only_supplied_fields(client, provider):
    etag = client.get(f"/agent/v1/providers/{provider.uuid}/")["ETag"]
    response = client.patch(
        f"/agent/v1/providers/{provider.uuid}/",
        json={"display_name": "Gemini"},
        headers={"If-Match": etag},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["display_name"] == "Gemini"
    assert data["model_prefix"] == "google-gla"


def test_delete_cascades_to_artifacts(client, provider, artifact):
    response = client.delete(f"/agent/v1/providers/{provider.uuid}/")
    assert response.status_code == 200
    assert response.json()["artifacts_deleted"] == 1
    assert not InferenceProvider.objects.filter(pk=provider.pk).exists()
    assert not ModelArtifact.objects.filter(pk=artifact.pk).exists()


def test_unknown_uuid_is_404(client):
    response = client.get("/agent/v1/providers/00000000-0000-0000-0000-000000000000/")
    assert response.status_code == 404
