"""User endpoints: list/search, create, detail, PATCH lifecycle."""

from __future__ import annotations

from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.core import mail

User = get_user_model()

CREATE_PAYLOAD = {
    "email": "maria@example.com",
    "first_name": "Maria",
    "last_name": "Papadopoulou",
    "born_at": "1990-04-23",
    "country": "GR",
    "phone_number": "+306912345678",
}


def _create(client, **overrides):
    payload = {**CREATE_PAYLOAD, **overrides}
    response = client.post("/users/v1/users/", json=payload)
    assert response.status_code == 201, response.json()
    return response


class TestListUsers:
    def test_list_returns_envelope_without_pks(self, client, superuser):
        response = client.get("/users/v1/users/")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        entry = data["users"][0]
        assert entry["email"] == superuser.email
        assert entry["full_name"] == "API Admin"
        assert "id" not in entry
        assert "uuid" in entry

    def test_is_active_filter(self, client, regular_user):
        regular_user.is_active = False
        regular_user.save()
        data = client.get("/users/v1/users/?is_active=false").json()
        assert [u["email"] for u in data["users"]] == [regular_user.email]

    def test_search_smoke(self, client):
        # The SQLite fallback search backend returns no matches — assert
        # the parameter is accepted, not what it finds.
        response = client.get("/users/v1/users/?search=maria")
        assert response.status_code == 200


class TestCreateUser:
    def test_create_full_profile(self, client, gender):
        response = _create(client, gender_uuid=str(gender.uuid))
        data = response.json()
        assert "id" not in data
        assert data["email"] == "maria@example.com"
        assert data["born_at"] == "1990-04-23"
        assert data["gender"] == {"uuid": str(gender.uuid), "name": gender.name}
        assert data["country"] == "GR"
        assert data["phone_number"] == "+306912345678"
        assert data["is_superuser"] is False
        assert response["ETag"].startswith('W/"')

        user = User.objects.get(uuid=data["uuid"])
        assert user.username  # allauth populated it

    def test_created_user_has_no_login_access_and_no_email_is_sent(self, client):
        data = _create(client).json()
        user = User.objects.get(uuid=data["uuid"])
        assert not user.has_usable_password()
        assert EmailAddress.objects.filter(user=user, email=user.email).exists()
        assert len(mail.outbox) == 0

    def test_password_in_payload_is_ignored(self, client):
        data = _create(client, password="hunter2!!").json()
        assert "password" not in data
        assert not User.objects.get(uuid=data["uuid"]).has_usable_password()

    def test_duplicate_email_is_422(self, client):
        _create(client)
        response = client.post("/users/v1/users/", json=CREATE_PAYLOAD)
        assert response.status_code == 422

    def test_bad_country_is_422(self, client):
        response = client.post("/users/v1/users/", json={**CREATE_PAYLOAD, "country": "Greece"})
        assert response.status_code == 422

    def test_bad_phone_is_422(self, client):
        response = client.post("/users/v1/users/", json={**CREATE_PAYLOAD, "phone_number": "12345"})
        assert response.status_code == 422

    def test_future_birth_date_is_422(self, client):
        response = client.post("/users/v1/users/", json={**CREATE_PAYLOAD, "born_at": "2999-01-01"})
        assert response.status_code == 422

    def test_malformed_date_is_422(self, client):
        response = client.post("/users/v1/users/", json={**CREATE_PAYLOAD, "born_at": "not-a-date"})
        assert response.status_code == 422

    def test_unknown_gender_uuid_is_404(self, client):
        response = client.post(
            "/users/v1/users/",
            json={**CREATE_PAYLOAD, "gender_uuid": "00000000-0000-0000-0000-000000000000"},
        )
        assert response.status_code == 404


class TestGetUser:
    def test_detail_sets_etag_and_hides_pk(self, client, gender):
        uuid = _create(client, gender_uuid=str(gender.uuid)).json()["uuid"]
        response = client.get(f"/users/v1/users/{uuid}/")
        assert response.status_code == 200
        data = response.json()
        assert "id" not in data
        assert data["age_display"]
        assert data["country_name"] == "Greece"
        assert response["ETag"].startswith('W/"')

    def test_unknown_uuid_is_404(self, client):
        response = client.get("/users/v1/users/00000000-0000-0000-0000-000000000000/")
        assert response.status_code == 404


class TestUpdateUser:
    def test_missing_if_match_is_428(self, client):
        uuid = _create(client).json()["uuid"]
        response = client.patch(f"/users/v1/users/{uuid}/", json={"first_name": "Ann"})
        assert response.status_code == 428

    def test_stale_etag_is_412(self, client):
        uuid = _create(client).json()["uuid"]
        response = client.patch(
            f"/users/v1/users/{uuid}/",
            json={"first_name": "Ann"},
            headers={"If-Match": 'W/"deadbeefdeadbeef"'},
        )
        assert response.status_code == 412

    def test_partial_update_with_fresh_etag(self, client):
        created = _create(client)
        uuid = created.json()["uuid"]
        response = client.patch(
            f"/users/v1/users/{uuid}/",
            json={"first_name": "Ann"},
            headers={"If-Match": created["ETag"]},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["first_name"] == "Ann"
        assert data["last_name"] == "Papadopoulou"  # untouched
        assert response["ETag"] != created["ETag"]

    def test_explicit_null_clears_nullable_fields(self, client, gender):
        created = _create(client, gender_uuid=str(gender.uuid))
        uuid = created.json()["uuid"]
        response = client.patch(
            f"/users/v1/users/{uuid}/",
            json={"phone_number": None, "gender_uuid": None, "born_at": None, "country": None},
            headers={"If-Match": created["ETag"]},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["phone_number"] is None
        assert data["gender"] is None
        assert data["born_at"] is None
        assert data["country"] is None

    def test_email_change_syncs_allauth_record(self, client):
        created = _create(client)
        uuid = created.json()["uuid"]
        response = client.patch(
            f"/users/v1/users/{uuid}/",
            json={"email": "maria.new@example.com"},
            headers={"If-Match": created["ETag"]},
        )
        assert response.status_code == 200
        user = User.objects.get(uuid=uuid)
        assert EmailAddress.objects.filter(user=user, email="maria.new@example.com").exists()
        assert not EmailAddress.objects.filter(user=user, email="maria@example.com").exists()
        assert len(mail.outbox) == 0

    def test_duplicate_email_is_422(self, client, regular_user):
        created = _create(client)
        uuid = created.json()["uuid"]
        response = client.patch(
            f"/users/v1/users/{uuid}/",
            json={"email": regular_user.email},
            headers={"If-Match": created["ETag"]},
        )
        assert response.status_code == 422

    def test_forbidden_fields_are_ignored(self, client):
        created = _create(client)
        uuid = created.json()["uuid"]
        response = client.patch(
            f"/users/v1/users/{uuid}/",
            json={
                "is_superuser": True,
                "is_staff": True,
                "password": "hacked",
                "first_name": "Still",
            },
            headers={"If-Match": created["ETag"]},
        )
        assert response.status_code == 200
        user = User.objects.get(uuid=uuid)
        assert user.first_name == "Still"
        assert user.is_superuser is False
        assert user.is_staff is False
        assert not user.has_usable_password()

    def test_username_is_writable(self, client):
        created = _create(client)
        uuid = created.json()["uuid"]
        response = client.patch(
            f"/users/v1/users/{uuid}/",
            json={"username": "maria.p"},
            headers={"If-Match": created["ETag"]},
        )
        assert response.status_code == 200
        assert response.json()["username"] == "maria.p"
        assert response["ETag"] != created["ETag"]  # username is etag-covered

    def test_deactivation_works_but_not_on_superusers(self, client, superuser):
        created = _create(client)
        uuid = created.json()["uuid"]
        response = client.patch(
            f"/users/v1/users/{uuid}/",
            json={"is_active": False},
            headers={"If-Match": created["ETag"]},
        )
        assert response.status_code == 200
        assert response.json()["is_active"] is False

        detail = client.get(f"/users/v1/users/{superuser.uuid}/")
        response = client.patch(
            f"/users/v1/users/{superuser.uuid}/",
            json={"is_active": False},
            headers={"If-Match": detail["ETag"]},
        )
        assert response.status_code == 422


class TestCreateUsername:
    def test_explicit_username_is_used(self, client):
        data = _create(client, username="maria.papadopoulou").json()
        assert data["username"] == "maria.papadopoulou"

    def test_omitted_username_is_autogenerated(self, client):
        data = _create(client).json()
        assert data["username"]

    def test_taken_username_is_422_case_insensitively(self, client, regular_user):
        response = client.post(
            "/users/v1/users/",
            json={**CREATE_PAYLOAD, "username": regular_user.username.upper()},
        )
        assert response.status_code == 422


class TestDeleteUser:
    def test_delete_removes_user_and_email_records(self, client):
        from allauth.account.models import EmailAddress

        uuid = _create(client).json()["uuid"]
        user = User.objects.get(uuid=uuid)
        response = client.delete(f"/users/v1/users/{uuid}/")
        assert response.status_code == 204
        assert not User.objects.filter(uuid=uuid).exists()
        assert not EmailAddress.objects.filter(user_id=user.pk).exists()

    def test_other_superusers_are_deletable(self, client, django_user_model):
        other = django_user_model.objects.create_superuser(
            username="other-admin",
            email="other-admin@example.com",
            password="irrelevant",
            first_name="Other",
            last_name="Admin",
        )
        response = client.delete(f"/users/v1/users/{other.uuid}/")
        assert response.status_code == 204
        assert not User.objects.filter(pk=other.pk).exists()

    def test_own_account_is_not_deletable(self, client, superuser):
        response = client.delete(f"/users/v1/users/{superuser.uuid}/")
        assert response.status_code == 422
        assert User.objects.filter(pk=superuser.pk).exists()

    def test_unknown_uuid_is_404(self, client):
        response = client.delete("/users/v1/users/00000000-0000-0000-0000-000000000000/")
        assert response.status_code == 404
