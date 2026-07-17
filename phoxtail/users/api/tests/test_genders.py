"""Gender endpoints: full CRUD with ETag lifecycle."""

from __future__ import annotations

from django.contrib.auth import get_user_model

from phoxtail.users.models import Gender

User = get_user_model()


def test_create_and_list(client):
    response = client.post("/users/v1/genders/", json={"name": "Female", "symbol": "F"})
    assert response.status_code == 201
    data = response.json()
    assert "id" not in data
    assert data["name"] == "Female"
    assert data["symbol"] == "F"
    assert response["ETag"].startswith('W/"')

    listing = client.get("/users/v1/genders/")
    assert listing.status_code == 200
    body = listing.json()
    assert body["total"] == 1
    assert body["genders"][0]["uuid"] == data["uuid"]
    assert "id" not in body["genders"][0]


def test_symbolless_genders_do_not_collide(client):
    # symbol is unique-but-nullable: empty submissions must store NULL.
    assert client.post("/users/v1/genders/", json={"name": "A", "symbol": ""}).status_code == 201
    assert client.post("/users/v1/genders/", json={"name": "B"}).status_code == 201


def test_duplicate_name_is_422(client, gender):
    response = client.post("/users/v1/genders/", json={"name": gender.name})
    assert response.status_code == 422


def test_get_sets_etag(client, gender):
    response = client.get(f"/users/v1/genders/{gender.uuid}/")
    assert response.status_code == 200
    assert response["ETag"].startswith('W/"')
    assert response.json()["symbol"] == "F"


def test_update_etag_lifecycle(client, gender):
    url = f"/users/v1/genders/{gender.uuid}/"

    assert client.patch(url, json={"name": "Woman"}).status_code == 428
    assert client.patch(url, json={"name": "Woman"}, headers={"If-Match": 'W/"stale"'}).status_code == 412

    etag = client.get(url)["ETag"]
    response = client.patch(url, json={"name": "Woman"}, headers={"If-Match": etag})
    assert response.status_code == 200
    assert response.json()["name"] == "Woman"
    assert response.json()["symbol"] == "F"  # untouched
    assert response["ETag"] != etag

    # Explicit null clears the symbol.
    response = client.patch(url, json={"symbol": None}, headers={"If-Match": response["ETag"]})
    assert response.status_code == 200
    assert response.json()["symbol"] is None


def test_delete_nulls_out_member_references(client, gender, regular_user):
    regular_user.gender = gender
    regular_user.save()

    response = client.delete(f"/users/v1/genders/{gender.uuid}/")
    assert response.status_code == 204
    assert not Gender.objects.filter(pk=gender.pk).exists()

    regular_user.refresh_from_db()
    assert regular_user.gender is None


def test_unknown_uuid_is_404(client):
    response = client.get("/users/v1/genders/00000000-0000-0000-0000-000000000000/")
    assert response.status_code == 404
