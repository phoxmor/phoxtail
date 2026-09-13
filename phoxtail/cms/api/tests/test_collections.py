"""What each collection endpoint asks of its caller.

**This is the one commit in the pass that widens access.** The endpoints
used to ask ``user.has_perm("wagtailcore.add_collection")``, and Wagtail
does not grant collections that way — it writes ``GroupCollectionPermission``
rows naming a group, a collection and an action, and ``has_perm`` never
reads them. So a user Wagtail genuinely permits was refused, and the only
callers who got through were those holding a *global* grant, which the
Wagtail admin has no way to give.

Every test below that admits someone asserts ``has_perm`` is False in the
same breath. Either half alone reads as ordinary coverage; together they are
the proof that the old check was wrong rather than merely different.
"""

from __future__ import annotations

import pytest


@pytest.fixture
def branch(db):
    """A collection to be granted on, with a child and a sibling.

    The sibling is what distinguishes a grant that descends from one that
    simply admits everything.
    """
    from wagtail.models import Collection

    root = Collection.get_first_root_node()
    branch = root.add_child(name="Marketing")
    branch.add_child(name="Campaigns")
    root.add_child(name="Legal")
    return Collection.objects.get(pk=branch.pk)


@pytest.fixture
def grant_on():
    """Grant one collection action on one collection, Wagtail's way."""
    from django.contrib.auth.models import Group, Permission
    from wagtail.models import GroupCollectionPermission

    def _grant(user, collection, *actions: str):
        group, _ = Group.objects.get_or_create(name="collection-grantees")
        user.groups.add(group)
        for action in actions:
            GroupCollectionPermission.objects.create(
                group=group,
                collection=collection,
                permission=Permission.objects.get(
                    content_type__app_label="wagtailcore",
                    codename=f"{action}_collection",
                ),
            )
        return type(user).objects.get(pk=user.pk)

    return _grant


def _child_of(collection, name):
    return collection.get_children().get(name=name)


class TestTheWidening:
    """A per-collection grantee is now admitted. They were not before."""

    def test_creating_under_a_granted_collection_is_allowed(self, raw_client, regular_user, grant_on, branch):
        user = grant_on(regular_user, branch, "add")
        assert user.has_perm("wagtailcore.add_collection") is False, "the old check would have refused this user"

        response = raw_client.post(
            "/cms/v1/collections/",
            json={"name": "Q3 Launch", "parent_id": branch.pk},
            user=user,
        )
        assert response.status_code == 201, response.json()

    def test_renaming_a_granted_collection_is_allowed(self, raw_client, regular_user, grant_on, branch):
        user = grant_on(regular_user, branch, "change")
        assert user.has_perm("wagtailcore.change_collection") is False

        response = raw_client.patch(
            f"/cms/v1/collections/{branch.pk}/",
            json={"name": "Marketing EMEA"},
            headers={"If-Match": "*"},
            user=user,
        )
        assert response.status_code == 200, response.json()

    def test_deleting_a_granted_empty_collection_is_allowed(self, raw_client, regular_user, grant_on, branch):
        empty = branch.add_child(name="Empty")
        user = grant_on(regular_user, branch, "delete")
        assert user.has_perm("wagtailcore.delete_collection") is False

        response = raw_client.delete(
            f"/cms/v1/collections/{empty.pk}/",
            headers={"If-Match": "*"},
            user=user,
        )
        assert response.status_code == 204


class TestTheGrantDescendsAndNoFurther:
    """A grant flows down. A test that grants on one node and checks only
    that node cannot tell descent from blanket access."""

    def test_it_reaches_a_child(self, raw_client, regular_user, grant_on, branch):
        user = grant_on(regular_user, branch, "change")
        child = _child_of(branch, "Campaigns")
        response = raw_client.patch(
            f"/cms/v1/collections/{child.pk}/",
            json={"name": "Campaigns 2026"},
            headers={"If-Match": "*"},
            user=user,
        )
        assert response.status_code == 200, response.json()

    def test_it_does_not_reach_a_sibling(self, raw_client, regular_user, grant_on, branch):
        from wagtail.models import Collection

        user = grant_on(regular_user, branch, "change")
        legal = Collection.objects.get(name="Legal")
        response = raw_client.patch(
            f"/cms/v1/collections/{legal.pk}/",
            json={"name": "Legal Renamed"},
            headers={"If-Match": "*"},
            user=user,
        )
        assert response.status_code == 403

    def test_it_does_not_reach_the_parent(self, raw_client, regular_user, grant_on, branch):
        """Grants descend only — holding one on a child says nothing upward."""
        from wagtail.models import Collection

        child = _child_of(branch, "Campaigns")
        user = grant_on(regular_user, child, "change")
        response = raw_client.patch(
            f"/cms/v1/collections/{branch.pk}/",
            json={"name": "Marketing Renamed"},
            headers={"If-Match": "*"},
            user=user,
        )
        assert response.status_code == 403
        assert Collection.objects.get(pk=branch.pk).name == "Marketing"


class TestOneActionDoesNotGrantAnother:
    def test_change_does_not_grant_delete(self, raw_client, regular_user, grant_on, branch):
        empty = branch.add_child(name="Empty")
        user = grant_on(regular_user, branch, "change")
        response = raw_client.delete(
            f"/cms/v1/collections/{empty.pk}/",
            headers={"If-Match": "*"},
            user=user,
        )
        assert response.status_code == 403
        assert "delete" in response.json()["detail"]

    def test_change_does_not_grant_adding(self, raw_client, regular_user, grant_on, branch):
        user = grant_on(regular_user, branch, "change")
        response = raw_client.post(
            "/cms/v1/collections/",
            json={"name": "New", "parent_id": branch.pk},
            user=user,
        )
        assert response.status_code == 403
        assert "add" in response.json()["detail"]


class TestReading:
    """Narrowed, not refused — and a lookup resolves within the narrowing."""

    def test_the_listing_shows_only_what_may_be_managed(self, raw_client, regular_user, grant_on, branch):
        user = grant_on(regular_user, branch, "change")
        body = raw_client.get("/cms/v1/collections/", user=user).json()
        names = {item["name"] for item in body["items"]}
        assert names == {"Marketing", "Campaigns"}
        assert "Legal" not in names
        assert "Root" not in names

    def test_a_caller_with_no_grants_sees_an_empty_listing(self, raw_client, regular_user, branch):
        """A true answer to "which may I manage", not a claim of forbidden."""
        body = raw_client.get("/cms/v1/collections/", user=regular_user).json()
        assert body == {"items": [], "total": 0}

    def test_an_unmanageable_collection_is_404_not_403(self, raw_client, regular_user, grant_on, branch):
        """So the ids cannot be swept to map a tree you cannot see."""
        from wagtail.models import Collection

        user = grant_on(regular_user, branch, "change")
        legal = Collection.objects.get(name="Legal")
        assert raw_client.get(f"/cms/v1/collections/{legal.pk}/", user=user).status_code == 404

    def test_a_descendant_of_a_granted_collection_reads_back(self, raw_client, regular_user, grant_on, branch):
        """The listing and the lookup must agree about the same node.

        The listing narrows with ``instances_user_has_any_permission_for``
        and the lookup resolves within the same queryset — but the two are
        exercised on different nodes everywhere else here, so a descendant
        that appears in the listing and then 404s on its own URL is exactly
        the inconsistency these tests would otherwise miss.
        """
        user = grant_on(regular_user, branch, "change")
        child = _child_of(branch, "Campaigns")

        listed = {item["name"] for item in raw_client.get("/cms/v1/collections/", user=user).json()["items"]}
        assert "Campaigns" in listed

        response = raw_client.get(f"/cms/v1/collections/{child.pk}/", user=user)
        assert response.status_code == 200, "listed but not fetchable — the two paths disagree"
        assert response.json()["name"] == "Campaigns"

    def test_a_managed_collection_reads_back(self, raw_client, regular_user, grant_on, branch):
        user = grant_on(regular_user, branch, "change")
        response = raw_client.get(f"/cms/v1/collections/{branch.pk}/", user=user)
        assert response.status_code == 200
        assert response.json()["name"] == "Marketing"

    def test_a_visible_child_still_reports_its_real_parent(self, raw_client, regular_user, grant_on, branch):
        """The narrowing hides rows, it must not rewrite the tree."""
        user = grant_on(regular_user, branch, "change")
        body = raw_client.get("/cms/v1/collections/", user=user).json()
        campaigns = next(i for i in body["items"] if i["name"] == "Campaigns")
        assert campaigns["parent_id"] == branch.pk


class TestTheRoot:
    """Narrowed like everything else, rather than excluded."""

    def test_it_is_hidden_from_someone_without_a_grant_on_it(self, raw_client, regular_user, grant_on, branch):
        user = grant_on(regular_user, branch, "add")
        names = {item["name"] for item in raw_client.get("/cms/v1/collections/", user=user).json()["items"]}
        assert "Root" not in names

    def test_creating_at_top_level_needs_a_grant_on_the_root(self, raw_client, regular_user, grant_on, branch):
        """parent_id omitted means the root, which is not a free pass."""
        user = grant_on(regular_user, branch, "add")
        response = raw_client.post("/cms/v1/collections/", json={"name": "Top Level"}, user=user)
        assert response.status_code == 403

    def test_a_grant_on_the_root_does_allow_it(self, raw_client, regular_user, grant_on):
        from wagtail.models import Collection

        user = grant_on(regular_user, Collection.get_first_root_node(), "add")
        response = raw_client.post("/cms/v1/collections/", json={"name": "Top Level"}, user=user)
        assert response.status_code == 201, response.json()


class TestMoving:
    """Reparenting asks two further questions, both of them Wagtail's."""

    def test_the_destination_must_be_addable(self, raw_client, regular_user, grant_on, branch):
        from wagtail.models import Collection

        child = _child_of(branch, "Campaigns")
        user = grant_on(regular_user, child, "change", "add")
        legal = Collection.objects.get(name="Legal")
        response = raw_client.patch(
            f"/cms/v1/collections/{child.pk}/",
            json={"parent_id": legal.pk},
            headers={"If-Match": "*"},
            user=user,
        )
        assert response.status_code == 403
        assert "add" in response.json()["detail"]

    def test_a_collection_carrying_your_own_grant_cannot_be_moved(self, raw_client, regular_user, grant_on, branch):
        """The privilege-escalation guard, copied from Wagtail's Edit view.

        A grant flows down, so moving the very node your grant names would
        change what your grant reaches. Wagtail drops the parent field from
        the form; the API refuses the reparent.
        """
        from wagtail.models import Collection

        root = Collection.get_first_root_node()
        user = grant_on(regular_user, root, "add", "change")
        user = grant_on(user, branch, "change")

        response = raw_client.patch(
            f"/cms/v1/collections/{branch.pk}/",
            json={"parent_id": Collection.objects.get(name="Legal").pk},
            headers={"If-Match": "*"},
            user=user,
        )
        assert response.status_code == 403
        assert "own permissions" in response.json()["detail"]

    def test_a_collection_below_your_grant_can_be_moved(self, raw_client, regular_user, grant_on, branch):
        """The guard is about the granted node itself, not its descendants."""
        user = grant_on(regular_user, branch, "add", "change")
        child = _child_of(branch, "Campaigns")
        destination = branch.add_child(name="Archive")

        response = raw_client.patch(
            f"/cms/v1/collections/{child.pk}/",
            json={"parent_id": destination.pk},
            headers={"If-Match": "*"},
            user=user,
        )
        assert response.status_code == 200, response.json()


class TestTheWagtailSeamsWeDependOn:
    """Tripwires for a Wagtail upgrade, not assertions about our code."""

    def test_the_private_move_helper_still_exists(self, db):
        """``may_move`` calls it because Wagtail's own Edit view does."""
        from phoxtail.cms.api.v1._permissions import collection_policy

        assert hasattr(collection_policy(), "_get_user_permission_objects_for_actions")

    def test_the_policy_is_still_the_per_collection_one(self, db):
        from wagtail.permission_policies.collections import CollectionManagementPermissionPolicy

        from phoxtail.cms.api.v1._permissions import collection_policy

        assert isinstance(collection_policy(), CollectionManagementPermissionPolicy)

    def test_manageable_is_exactly_what_wagtails_listing_asks(self, db):
        """Read out of Wagtail's Index view rather than trusted from a comment.

        Nothing in the behavioural tests pins this list: no grant of
        ``view_collection`` exists to be found, so adding "view" to it
        changes no outcome while quietly meaning something different. If
        Wagtail ever grows a read action, this fails and reading should ask
        for it rather than narrowing.
        """
        from wagtail.admin.views.collections import Index

        from phoxtail.cms.api.v1._permissions import MANAGEABLE

        asked = next(c for c in Index.get_queryset.__code__.co_consts if isinstance(c, tuple | list) and "add" in c)
        assert list(asked) == MANAGEABLE


class TestTheCredentialHalf:
    """Both halves on a per-object family, for the first time in this pass."""

    def test_a_token_naming_the_act_is_admitted(self, raw_client, regular_user, grant_on, branch, scoped_token):
        user = grant_on(regular_user, branch, "change")
        headers = scoped_token(user, "wagtailcore.change_collection")
        response = raw_client.patch(
            f"/cms/v1/collections/{branch.pk}/",
            json={"name": "Marketing EMEA"},
            headers={**headers, "If-Match": "*"},
        )
        assert response.status_code == 200, response.json()

    def test_a_token_naming_something_else_is_refused(self, raw_client, regular_user, grant_on, branch, scoped_token):
        """The person may act and the token may not — still a refusal."""
        user = grant_on(regular_user, branch, "change")
        headers = scoped_token(user, "wagtailcore.view_collection")
        response = raw_client.patch(
            f"/cms/v1/collections/{branch.pk}/",
            json={"name": "Marketing EMEA"},
            headers={**headers, "If-Match": "*"},
        )
        assert response.status_code == 403
        assert "scopes" in response.json()["detail"]

    def test_the_token_alone_does_not_grant_the_permission(self, raw_client, regular_user, branch, scoped_token):
        """Minting does not require holding what it names, so a token naming
        change_collection must not confer it on someone with no grant."""
        headers = scoped_token(regular_user, "wagtailcore.change_collection")
        response = raw_client.patch(
            f"/cms/v1/collections/{branch.pk}/",
            json={"name": "Nope"},
            headers={**headers, "If-Match": "*"},
        )
        assert response.status_code == 403


@pytest.mark.urls("phoxtail.cms.tests.admin_urls")
class TestDeletionAsksWagtailWhatIsInside:
    """The API must refuse exactly what the admin refuses.

    Runs under a urlconf that mounts the Wagtail admin, because the hooks
    reverse admin routes to build the ``url`` on each answer — see that
    module's docstring. The hooks run for real here rather than mocked.

    ``delete_collection`` used to count images, documents and media itself.
    Wagtail's own delete view asks the ``describe_collection_contents``
    hook — the extension point any installed app may register against — so
    a hand-written count silently misses whatever it does not know about,
    and the API would delete a collection the admin refuses to.
    """

    def test_an_empty_collection_deletes(self, raw_client, superuser, branch):
        empty = branch.add_child(name="Empty")
        response = raw_client.delete(f"/cms/v1/collections/{empty.pk}/", headers={"If-Match": "*"}, user=superuser)
        assert response.status_code == 204

    def test_a_collection_with_a_descendant_is_refused(self, raw_client, superuser, branch):
        """The hook counts the whole subtree, which is stricter than the
        direct-children check it replaces."""
        response = raw_client.delete(f"/cms/v1/collections/{branch.pk}/", headers={"If-Match": "*"}, user=superuser)
        assert response.status_code == 409
        assert "descendant collection" in response.json()["detail"]

    def test_a_collection_holding_an_image_is_refused(self, raw_client, superuser, branch, db):
        """The case the old count did get right, kept so the swap is safe."""
        from wagtail.images import get_image_model

        empty = branch.add_child(name="Has An Image")
        get_image_model().objects.create(
            title="logo", collection=empty, file="original_images/x.png", width=1, height=1
        )

        response = raw_client.delete(f"/cms/v1/collections/{empty.pk}/", headers={"If-Match": "*"}, user=superuser)
        assert response.status_code == 409
        assert "image" in response.json()["detail"]

    def test_a_hook_answering_zero_does_not_block(self, raw_client, superuser, branch, monkeypatch):
        """Wagtail's own filter: None, or a zero count, is not occupancy.

        Dropping that filter would make every collection undeletable, and
        only a hook that answers about an empty collection reveals it.
        """
        from wagtail import hooks

        empty = branch.add_child(name="Empty")
        real = hooks.get_hooks

        def with_a_quiet_hook(name):
            if name == "describe_collection_contents":
                return [*real(name), lambda c: None, lambda c: {"count": 0, "count_text": "0 widgets"}]
            return real(name)

        monkeypatch.setattr(hooks, "get_hooks", with_a_quiet_hook)
        response = raw_client.delete(f"/cms/v1/collections/{empty.pk}/", headers={"If-Match": "*"}, user=superuser)
        assert response.status_code == 204

    def test_a_third_party_hook_is_honoured(self, raw_client, superuser, branch, monkeypatch):
        """The whole point: an app we know nothing about can refuse a delete."""
        from wagtail import hooks

        empty = branch.add_child(name="Empty")
        real = hooks.get_hooks

        def with_a_loud_hook(name):
            if name == "describe_collection_contents":
                return [*real(name), lambda c: {"count": 3, "count_text": "3 invoices"}]
            return real(name)

        monkeypatch.setattr(hooks, "get_hooks", with_a_loud_hook)
        response = raw_client.delete(f"/cms/v1/collections/{empty.pk}/", headers={"If-Match": "*"}, user=superuser)
        assert response.status_code == 409
        assert "3 invoices" in response.json()["detail"]
