"""Email verification endpoints: single and bulk, allauth record effects."""

from __future__ import annotations

from allauth.account.models import EmailAddress
from django.core import mail

from .test_users import CREATE_PAYLOAD


def _create_uuid(client) -> str:
    return client.post("/users/v1/users/", json=CREATE_PAYLOAD).json()["uuid"]


class TestVerifyEmail:
    def test_verify_flips_the_allauth_record(self, client):
        uuid = _create_uuid(client)
        assert client.get(f"/users/v1/users/{uuid}/").json()["email_verified"] is False

        response = client.post(f"/users/v1/users/{uuid}/verify-email/")
        assert response.status_code == 200
        data = response.json()
        assert data == {"uuid": uuid, "email": CREATE_PAYLOAD["email"], "status": "verified"}

        record = EmailAddress.objects.get(email=CREATE_PAYLOAD["email"])
        assert record.verified is True
        assert record.primary is True
        assert client.get(f"/users/v1/users/{uuid}/").json()["email_verified"] is True
        assert len(mail.outbox) == 0

    def test_verify_is_idempotent(self, client):
        uuid = _create_uuid(client)
        client.post(f"/users/v1/users/{uuid}/verify-email/")
        response = client.post(f"/users/v1/users/{uuid}/verify-email/")
        assert response.status_code == 200
        assert response.json()["status"] == "already_verified"

    def test_missing_record_is_created(self, client, regular_user):
        # ORM-created users have no EmailAddress row at all.
        assert not EmailAddress.objects.filter(user=regular_user).exists()
        response = client.post(f"/users/v1/users/{regular_user.uuid}/verify-email/")
        assert response.status_code == 200
        assert response.json()["status"] == "verified"
        assert EmailAddress.objects.get(user=regular_user, email=regular_user.email).verified is True

    def test_unknown_uuid_is_404(self, client):
        response = client.post("/users/v1/users/00000000-0000-0000-0000-000000000000/verify-email/")
        assert response.status_code == 404


class TestBulkVerifyEmails:
    def test_mixed_rows_are_independent(self, client, regular_user, superuser):
        unknown = "00000000-0000-0000-0000-000000000000"
        client.post(f"/users/v1/users/{superuser.uuid}/verify-email/")

        response = client.post(
            "/users/v1/users/verify-emails/",
            json={"user_uuids": [str(regular_user.uuid), unknown, str(superuser.uuid)]},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["verified"] == 1
        assert data["already_verified"] == 1
        assert data["failed"] == 1

        by_index = {r["index"]: r for r in data["results"]}
        assert by_index[0]["status"] == "verified"
        assert by_index[0]["email"] == regular_user.email
        assert by_index[1]["status"] == "error"
        assert by_index[1]["detail"]
        assert by_index[2]["status"] == "already_verified"
        assert len(mail.outbox) == 0

    def test_row_cap_is_enforced(self, client):
        uuids = ["00000000-0000-0000-0000-000000000000"] * 101
        response = client.post("/users/v1/users/verify-emails/", json={"user_uuids": uuids})
        assert response.status_code == 422
        assert "100" in response.json()["detail"]
