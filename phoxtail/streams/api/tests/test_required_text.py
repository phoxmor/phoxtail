"""Text the model requires is required by the schema too.

A blank value used to reach the model's own validation and come back as an
opaque 400; the schema now refuses it first, as 422 naming the field, and
the OpenAPI document no longer calls the field optional.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.django_db


def _refused_for(response, field):
    assert response.status_code == 422
    return any(field in error["loc"] for error in response.json()["detail"])


@pytest.mark.parametrize(
    "path, body, field",
    [
        ("/streams/v1/collections/", {"identifier": "one", "name": "One"}, "description"),
        ("/streams/v1/collections/", {"identifier": "", "name": "One", "description": "d"}, "identifier"),
        ("/streams/v1/blocks/", {"identifier": "one", "name": "One"}, "description"),
        ("/streams/v1/blocks/", {"identifier": "one", "name": "", "description": "d"}, "name"),
        ("/streams/v1/block-categories/", {"name": "", "slug": "one"}, "name"),
        ("/streams/v1/block-categories/", {"name": "One", "slug": ""}, "slug"),
    ],
)
def test_creating_without_required_text_names_the_field(client, path, body, field):
    assert _refused_for(client.post(path, json=body), field)


def test_a_block_category_may_still_omit_its_description(client):
    # The one text field here the model leaves optional.
    assert client.post("/streams/v1/block-categories/", json={"name": "One", "slug": "one"}).status_code == 201


@pytest.mark.parametrize(
    "path, body, change, field",
    [
        (
            "/streams/v1/collections/",
            {"identifier": "one", "name": "One", "description": "d"},
            {"description": ""},
            "description",
        ),
        ("/streams/v1/blocks/", {"identifier": "one", "name": "One", "description": "d"}, {"name": ""}, "name"),
        ("/streams/v1/block-categories/", {"name": "One", "slug": "one"}, {"slug": ""}, "slug"),
    ],
)
def test_blanking_required_text_on_update_names_the_field(client, path, body, change, field):
    created = client.post(path, json=body)
    assert created.status_code == 201

    response = client.patch(f"{path}{created.json()['id']}/", json=change, headers={"If-Match": created["ETag"]})

    assert _refused_for(response, field)
