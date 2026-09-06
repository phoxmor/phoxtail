"""Menu endpoints: full CRUD with ETag lifecycle."""

from __future__ import annotations

import json

HOME = [{"type": "external_link", "value": {"url": "https://example.com", "label": "Home"}}]


def test_create_and_list(client, site, locale):
    response = client.post(
        "/dashboard/v1/menus/",
        json={"site_id": site.id, "locale_id": locale.id, "items": HOME},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["language_code"] == locale.language_code
    assert data["entry_count"] == 1
    assert json.loads(data["items"])[0]["type"] == "external_link"
    assert response["ETag"].startswith('W/"')

    listing = client.get("/dashboard/v1/menus/")
    assert listing.status_code == 200
    assert listing.json()["total"] == 1


def test_one_menu_per_site_and_language(client, site, locale):
    assert client.post("/dashboard/v1/menus/", json={"site_id": site.id, "locale_id": locale.id}).status_code == 201
    duplicate = client.post("/dashboard/v1/menus/", json={"site_id": site.id, "locale_id": locale.id})
    assert duplicate.status_code == 409


def test_list_filters_by_locale(client, site, locale, greek):
    client.post("/dashboard/v1/menus/", json={"site_id": site.id, "locale_id": locale.id})
    client.post("/dashboard/v1/menus/", json={"site_id": site.id, "locale_id": greek.id})

    filtered = client.get(f"/dashboard/v1/menus/?locale={greek.id}")
    assert filtered.json()["total"] == 1
    assert filtered.json()["menus"][0]["language_code"] == "el"


def test_unknown_locale_is_404(client, site):
    assert client.post("/dashboard/v1/menus/", json={"site_id": site.id, "locale_id": 9999}).status_code == 404


def test_update_replaces_the_entries(client, site, locale):
    created = client.post("/dashboard/v1/menus/", json={"site_id": site.id, "locale_id": locale.id})
    menu_uuid = created.json()["uuid"]
    etag = created["ETag"]

    updated = client.patch(
        f"/dashboard/v1/menus/{menu_uuid}/",
        json={"items": HOME},
        headers={"If-Match": etag},
    )
    assert updated.status_code == 200
    assert updated.json()["entry_count"] == 1
    assert updated["ETag"] != etag


def test_update_without_etag_is_428(client, site, locale):
    created = client.post("/dashboard/v1/menus/", json={"site_id": site.id, "locale_id": locale.id})
    menu_uuid = created.json()["uuid"]
    assert client.patch(f"/dashboard/v1/menus/{menu_uuid}/", json={"items": HOME}).status_code == 428


def test_update_with_stale_etag_is_412(client, site, locale):
    created = client.post("/dashboard/v1/menus/", json={"site_id": site.id, "locale_id": locale.id})
    menu_uuid = created.json()["uuid"]
    stale = created["ETag"]

    client.patch(f"/dashboard/v1/menus/{menu_uuid}/", json={"items": HOME}, headers={"If-Match": stale})
    again = client.patch(f"/dashboard/v1/menus/{menu_uuid}/", json={"items": []}, headers={"If-Match": stale})
    assert again.status_code == 412


def test_delete(client, site, locale):
    created = client.post("/dashboard/v1/menus/", json={"site_id": site.id, "locale_id": locale.id})
    menu_uuid = created.json()["uuid"]

    assert client.delete(f"/dashboard/v1/menus/{menu_uuid}/").status_code == 204
    assert client.get(f"/dashboard/v1/menus/{menu_uuid}/").status_code == 404


def test_an_unknown_entry_type_is_refused(client, site, locale):
    """Wagtail would drop it silently and answer 200 with an emptied menu."""
    response = client.post(
        "/dashboard/v1/menus/",
        json={"site_id": site.id, "locale_id": locale.id, "items": [{"type": "nope", "value": {}}]},
    )

    assert response.status_code == 422
    assert "unknown entry type" in response.json()["detail"]


def test_an_unknown_type_inside_a_dropdown_is_refused(client, site, locale):
    dropdown = [{"type": "dropdown", "value": {"label": "More", "items": [{"type": "nope", "value": {}}]}}]

    response = client.post(
        "/dashboard/v1/menus/",
        json={"site_id": site.id, "locale_id": locale.id, "items": dropdown},
    )

    assert response.status_code == 422
    assert "items[0].items[0]" in response.json()["detail"]
