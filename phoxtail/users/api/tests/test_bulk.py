"""``POST /users/bulk/`` — the CSV member-import endpoint."""

from __future__ import annotations

from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.core import mail

User = get_user_model()


def _row(i: int, **overrides) -> dict:
    return {
        "email": f"member{i}@example.com",
        "first_name": f"Member{i}",
        "last_name": "Imported",
        **overrides,
    }


def test_bulk_create_happy_path(client, gender):
    rows = [
        _row(0, born_at="1985-02-11", country="GR", phone_number="+306912345670"),
        _row(1, gender_uuid=str(gender.uuid)),
        _row(2),
    ]
    response = client.post("/users/v1/users/bulk/", json={"users": rows})
    assert response.status_code == 200
    data = response.json()
    assert data["created"] == 3
    assert data["failed"] == 0
    for index, result in enumerate(data["results"]):
        assert result["index"] == index
        assert result["status"] == "created"
        assert result["uuid"]
        assert "id" not in result
        user = User.objects.get(uuid=result["uuid"])
        assert not user.has_usable_password()
        assert EmailAddress.objects.filter(user=user).exists()
    assert len(mail.outbox) == 0


def test_bad_rows_are_reported_without_aborting_the_batch(client):
    rows = [
        _row(0),
        _row(1, email="member0@example.com"),  # duplicate of row 0
        _row(2, gender_uuid="00000000-0000-0000-0000-000000000000"),
        _row(3, country="Greece"),
        _row(4),
    ]
    response = client.post("/users/v1/users/bulk/", json={"users": rows})
    assert response.status_code == 200
    data = response.json()
    assert data["created"] == 2
    assert data["failed"] == 3

    by_index = {r["index"]: r for r in data["results"]}
    assert by_index[0]["status"] == "created"
    assert by_index[4]["status"] == "created"
    for failing in (1, 2, 3):
        assert by_index[failing]["status"] == "error"
        assert by_index[failing]["uuid"] is None
        assert by_index[failing]["detail"]
    assert by_index[1]["email"] == "member0@example.com"

    # Failed rows left no trace behind.
    assert not User.objects.filter(email="member2@example.com").exists()
    assert not User.objects.filter(email="member3@example.com").exists()


def test_row_cap_is_enforced(client):
    rows = [_row(i) for i in range(101)]
    response = client.post("/users/v1/users/bulk/", json={"users": rows})
    assert response.status_code == 422
    assert "100" in response.json()["detail"]
    assert not User.objects.filter(email__startswith="member").exists()
