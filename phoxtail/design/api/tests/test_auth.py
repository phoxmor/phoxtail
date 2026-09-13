"""What each design endpoint asks of its caller.

All thirty asked for nothing beyond being authenticated: any account with a
session or an unrestricted token could rewrite the palettes and fonts every
page on the site renders with.

Each now names the permission its act needs. The six models are plain —
verified rather than assumed, since media turned out not to be: every one
carries a registered ``ModelPermissionPolicy`` under this app's own label, so
``has_perm`` is the whole answer and ``guarded()`` is the right tool.

One set per codename rather than per endpoint. Whether an endpoint was missed
is a different question, answered by ``test_tool_scopes.py`` reading the
annotations; these check that the codename chosen for an act is the right one
and grants nothing next to it.
"""

from __future__ import annotations

import pytest

# One readable collection per resource, and the codename that opens it. Six
# resources, because a permission on one must not reach any of the other five.
READS = {
    "/design/v1/palette-sets/": "view_paletteset",
    "/design/v1/palettes/": "view_palette",
    "/design/v1/palette-roles/": "view_paletterole",
    "/design/v1/font-families/": "view_fontfamily",
    "/design/v1/font-roles/": "view_fontrole",
    "/design/v1/font-weights/": "view_fontweight",
}


def test_unauthenticated_request_is_401(db, raw_client):
    """No caller at all is a different event from the wrong caller."""
    assert raw_client.get("/design/v1/palettes/").status_code == 401


@pytest.mark.parametrize("path,codename", sorted(READS.items()))
def test_reading_without_the_permission_is_403(raw_client, regular_user, path, codename):
    response = raw_client.get(path, user=regular_user)
    assert response.status_code == 403
    assert codename in response.json()["detail"]


@pytest.mark.parametrize("path,codename", sorted(READS.items()))
def test_reading_with_the_permission_is_allowed(raw_client, regular_user, grant, path, codename):
    """The widening this commit is for: no superuser flag involved."""
    user = grant(regular_user, codename)
    assert raw_client.get(path, user=user).status_code == 200


@pytest.mark.parametrize("path,codename", sorted(READS.items()))
def test_one_resource_does_not_open_the_others(raw_client, regular_user, grant, path, codename):
    """Six models, six grants. The one mistake a copy-paste pass would make."""
    user = grant(regular_user, codename)
    for other, other_codename in READS.items():
        expected = 200 if other == path else 403
        assert raw_client.get(other, user=user).status_code == expected, (path, other)


def test_reading_does_not_grant_creating(raw_client, regular_user, grant):
    user = grant(regular_user, "view_paletterole")
    response = raw_client.post(
        "/design/v1/palette-roles/",
        json={"name": "Accent", "identifier": "accent"},
        user=user,
    )
    assert response.status_code == 403
    assert "add_paletterole" in response.json()["detail"]


def test_creating_does_not_grant_changing(raw_client, regular_user, grant):
    role = _a_palette_role()
    user = grant(regular_user, "add_paletterole")
    response = raw_client.patch(
        f"/design/v1/palette-roles/{role.id}/",
        json={"name": "Renamed"},
        headers={"If-Match": "*"},
        user=user,
    )
    assert response.status_code == 403
    assert "change_paletterole" in response.json()["detail"]


def test_changing_does_not_grant_deleting(raw_client, regular_user, grant):
    """The act this pass most exists for — it used to need no permission."""
    role = _a_palette_role()
    user = grant(regular_user, "change_paletterole")
    response = raw_client.delete(f"/design/v1/palette-roles/{role.id}/", user=user)
    assert response.status_code == 403
    assert "delete_paletterole" in response.json()["detail"]


def test_deleting_with_the_permission_is_allowed(raw_client, regular_user, grant):
    from phoxtail.design.models import PaletteRole

    role = _a_palette_role()
    user = grant(regular_user, "delete_paletterole")
    # These endpoints keep their read-before-write ETag contract; the header
    # is about concurrency, not authorization, and is unrelated to this pass.
    response = raw_client.delete(
        f"/design/v1/palette-roles/{role.id}/",
        headers={"If-Match": "*"},
        user=user,
    )
    assert response.status_code == 204
    assert not PaletteRole.objects.filter(pk=role.pk).exists()


def test_superuser_is_still_admitted(client):
    """Unchanged for them: Django answers has_perm True for a superuser."""
    assert client.get("/design/v1/palettes/").status_code == 200


def _a_palette_role():
    from phoxtail.design.models import PaletteRole

    return PaletteRole.objects.create(name="Surface", identifier="surface")
