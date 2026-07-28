"""Agent site settings: auto-create on read, set and clear the default model."""

from __future__ import annotations


def test_get_auto_creates_blank_settings(client, site):
    response = client.get(f"/agent/v1/settings/{site.pk}/")
    assert response.status_code == 200
    assert response.json() == {"site_id": site.pk, "default_artifact": None}
    assert response["ETag"].startswith('W/"')


def test_unknown_site_is_404(client, db):
    assert client.get("/agent/v1/settings/9999/").status_code == 404


def test_update_requires_if_match(client, site, artifact):
    response = client.patch(
        f"/agent/v1/settings/{site.pk}/",
        json={"default_artifact_uuid": str(artifact.uuid)},
    )
    assert response.status_code == 428


def test_set_and_clear_default(client, site, artifact):
    etag = client.get(f"/agent/v1/settings/{site.pk}/")["ETag"]
    response = client.patch(
        f"/agent/v1/settings/{site.pk}/",
        json={"default_artifact_uuid": str(artifact.uuid)},
        headers={"If-Match": etag},
    )
    assert response.status_code == 200
    assert response.json()["default_artifact"]["uuid"] == str(artifact.uuid)

    cleared = client.patch(
        f"/agent/v1/settings/{site.pk}/",
        json={"default_artifact_uuid": None},
        headers={"If-Match": response["ETag"]},
    )
    assert cleared.status_code == 200
    assert cleared.json()["default_artifact"] is None


def test_unknown_artifact_is_404(client, site):
    etag = client.get(f"/agent/v1/settings/{site.pk}/")["ETag"]
    response = client.patch(
        f"/agent/v1/settings/{site.pk}/",
        json={"default_artifact_uuid": "00000000-0000-0000-0000-000000000000"},
        headers={"If-Match": etag},
    )
    assert response.status_code == 404
