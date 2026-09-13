"""What each streams endpoint asks of its caller.

All of them asked for nothing beyond being authenticated: any account with a
session or an unrestricted token could rewrite every block, variant and
shared block the site is built from.

The five models are plain — verified rather than assumed, since media turned
out not to be: each carries a registered ``ModelPermissionPolicy`` under this
app's own label, so ``has_perm`` is the whole answer.

One set per codename rather than per endpoint. Whether an endpoint was missed
is a different question, answered by ``test_tool_scopes.py``; these check
that the codename chosen for an act is the right one and grants nothing next
to it.
"""

from __future__ import annotations

import pytest

# One readable collection per model, and the codename that opens it.
READS = {
    "/streams/v1/blocks/": "view_block",
    "/streams/v1/block-categories/": "view_blockcategory",
    "/streams/v1/collections/": "view_variantcollection",
    "/streams/v1/variants/": "view_blockvariant",
    "/streams/v1/shared-blocks/": "view_sharedblock",
}


def test_unauthenticated_request_is_401(db, raw_client):
    """No caller at all is a different event from the wrong caller."""
    assert raw_client.get("/streams/v1/blocks/").status_code == 401


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
def test_one_model_does_not_open_the_others(raw_client, regular_user, grant, path, codename):
    """Five models, five grants. The one mistake a copy-paste pass would make."""
    user = grant(regular_user, codename)
    for other, _ in READS.items():
        expected = 200 if other == path else 403
        assert raw_client.get(other, user=user).status_code == expected, (path, other)


def test_reading_does_not_grant_creating(raw_client, regular_user, grant):
    user = grant(regular_user, "view_blockcategory")
    response = raw_client.post(
        "/streams/v1/block-categories/",
        json={"name": "Heroes", "slug": "heroes"},
        user=user,
    )
    assert response.status_code == 403
    assert "add_blockcategory" in response.json()["detail"]


def test_changing_does_not_grant_deleting(raw_client, regular_user, grant, category):
    """The act this pass most exists for — it used to need no permission."""
    user = grant(regular_user, "change_blockcategory")
    response = raw_client.delete(
        f"/streams/v1/block-categories/{category.id}/",
        headers={"If-Match": "*"},
        user=user,
    )
    assert response.status_code == 403
    assert "delete_blockcategory" in response.json()["detail"]


class TestCategorisingABlock:
    """Putting a block in a category is a change to the *block*.

    Django has no implicit rule that referencing a row requires permission
    over it — ``has_perm`` is one boolean about one act. Wagtail invented
    ``choose_*`` for exactly that question, but only for snippets, images and
    documents; ``BlockCategory`` has no such row, so asking for one would be
    inventing the rule rather than following it.

    The practical consequence is real and deliberate: without
    ``view_blockcategory`` a caller cannot *discover* category ids, only use
    ones they already know. That is a usability limit, not a hole.

    **When the opposite applies.** The media endpoints do ask about the row
    they reference: moving a file into a collection requires ``add`` on the
    destination, because otherwise change-here would imply add-anywhere. The
    difference is not taste. A Wagtail ``Collection`` carries grants of its
    own — ``(group, collection, permission)`` rows — so "may I put something
    here" is a question the system can answer. ``BlockCategory`` and
    ``VariantCollection`` are plain models with no per-object grants, so
    there is nothing to ask and naming a codename would only be a second
    global check wearing the costume of a local one.

    So the rule, which cms will need for pages: **referencing a row asks
    nothing about it, unless that row type carries its own per-object
    grants.** ``create_variant`` and ``update_variant_by_id`` take a
    ``block_id`` and a ``collection_id`` and are annotated accordingly —
    they resolve and assign, and neither model grants per object.
    """

    def test_it_needs_change_block(self, raw_client, regular_user, grant, block, category):
        user = grant(regular_user, "change_blockcategory")
        response = raw_client.post(
            f"/streams/v1/blocks/{block.id}/categories/{category.id}/",
            user=user,
        )
        assert response.status_code == 403
        assert "change_block" in response.json()["detail"]

    def test_change_block_is_enough(self, raw_client, regular_user, grant, block, category):
        """No permission over the category is required, and none is asked."""
        user = grant(regular_user, "change_block")
        response = raw_client.post(
            f"/streams/v1/blocks/{block.id}/categories/{category.id}/",
            user=user,
        )
        assert response.status_code in (200, 201, 204), response.content

    def test_reading_a_block_s_categories_needs_view_block(self, raw_client, regular_user, grant, block):
        user = grant(regular_user, "view_block")
        assert raw_client.get(f"/streams/v1/blocks/{block.id}/categories/", user=user).status_code == 200


class TestTheCataloguesAreDeliberatelyUngated:
    """Two endpoints name no codename, and that is the decision, not a miss.

    Neither exposes project data. ``schema-catalog`` introspects this app's
    own field, structure and layer block classes — it is the vocabulary for
    writing a schema, and an agent reads it to know what it may write.
    ``page-types`` lists the app labels present in Django's ContentType
    table, which the CLI uses for a pre-flight check before loading a dump.

    Declaring no scope is not an omission here: the API-wide default refuses
    a scoped token outright and admits sessions and unrestricted ones, so
    forgetting to annotate leaves a door closed rather than open.
    """

    @pytest.mark.parametrize("path", ["/streams/v1/schema-catalog/", "/streams/v1/page-types/"])
    def test_any_authenticated_caller_may_read_them(self, raw_client, regular_user, path):
        assert raw_client.get(path, user=regular_user).status_code == 200

    @pytest.mark.parametrize("path", ["/streams/v1/schema-catalog/", "/streams/v1/page-types/"])
    def test_but_not_an_unauthenticated_one(self, db, raw_client, path):
        assert raw_client.get(path).status_code == 401


def test_superuser_is_still_admitted(client):
    """Unchanged for them: Django answers has_perm True for a superuser."""
    assert client.get("/streams/v1/blocks/").status_code == 200
