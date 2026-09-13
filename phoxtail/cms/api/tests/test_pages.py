"""What each page endpoint asks of its caller.

Pages are the object-level family at its sharpest. Wagtail grants them per
**subtree**, through ``GroupPagePermission`` rows, and the grant covers
everything beneath the page it names. ``has_perm`` never reads those rows, so
every test here that admits someone asserts ``has_perm`` is False beside it —
the pair is the proof, and pages is where it surprises a reader most.

**The reads are the new part.** They had no check at all: any account that
could log in could read every page in the project, and read it as its *latest
draft*, because ``resolve_page_for_read`` surfaces unpublished revisions. So
the question these endpoints answer is not "may I see this page" but "may I
see this page's unreviewed edits".

That is why they narrow to the permission set and not to
``explorable_instances``. Wagtail's explorer set adds the *ancestors* of
every granted page so the tree can be walked to reach your subtree — its own
comment says so — and using it here would have handed a section editor the
drafts of every page above them. ``TestTheAncestorIsNotReadable`` is that
distinction, and it is the one decision in this commit that a reasonable
person could have got wrong.
"""

from __future__ import annotations

import pytest


@pytest.fixture
def tree(db):
    """Home > [Marketing > Campaigns], Legal.

    A subtree to grant on, a descendant to prove the grant flows down, a
    sibling to prove it does not flow sideways, and an ancestor to prove it
    does not flow up.
    """
    from wagtail.models import Page

    from phoxtail.cms.models import SitePage

    home = Page.objects.get(depth=2)
    marketing = home.add_child(instance=SitePage(title="Marketing", slug="marketing"))
    campaigns = marketing.add_child(instance=SitePage(title="Campaigns", slug="campaigns"))
    legal = home.add_child(instance=SitePage(title="Legal", slug="legal"))
    return {
        "home": Page.objects.get(pk=home.pk),
        "marketing": Page.objects.get(pk=marketing.pk),
        "campaigns": Page.objects.get(pk=campaigns.pk),
        "legal": Page.objects.get(pk=legal.pk),
    }


@pytest.fixture
def grant_page():
    """Grant page actions on one subtree, Wagtail's way."""
    from django.contrib.auth.models import Group, Permission
    from wagtail.models import GroupPagePermission

    def _grant(user, page, *actions: str):
        group, _ = Group.objects.get_or_create(name="page-grantees")
        user.groups.add(group)
        for action in actions:
            GroupPagePermission.objects.create(
                group=group,
                page=page,
                permission=Permission.objects.get(
                    content_type__app_label="wagtailcore",
                    codename=f"{action}_page",
                ),
            )
        return type(user).objects.get(pk=user.pk)

    return _grant


class TestReadingWasUngated:
    """The hole this closes: every page, as its unpublished draft."""

    def test_listing_without_a_grant_shows_nothing(self, raw_client, regular_user, tree):
        body = raw_client.get("/cms/v1/pages/", user=regular_user).json()
        assert body["pages"] == []
        assert body["total"] == 0

    def test_a_subtree_grantee_sees_their_subtree(self, raw_client, regular_user, grant_page, tree):
        user = grant_page(regular_user, tree["marketing"], "change")
        assert user.has_perm("wagtailcore.change_page") is False, "guarded() would have refused this user"

        titles = {p["title"] for p in raw_client.get("/cms/v1/pages/", user=user).json()["pages"]}
        assert titles == {"Marketing", "Campaigns"}

    def test_reading_one_page_in_the_subtree_is_allowed(self, raw_client, regular_user, grant_page, tree):
        user = grant_page(regular_user, tree["marketing"], "change")
        response = raw_client.get(f"/cms/v1/pages/{tree['campaigns'].pk}/", user=user)
        assert response.status_code == 200
        assert response.json()["title"] == "Campaigns"

    def test_a_sibling_subtree_is_404(self, raw_client, regular_user, grant_page, tree):
        """404 rather than 403, so ids cannot be swept to map the tree."""
        user = grant_page(regular_user, tree["marketing"], "change")
        assert raw_client.get(f"/cms/v1/pages/{tree['legal'].pk}/", user=user).status_code == 404

    def test_the_body_and_block_reads_use_the_same_gate(self, raw_client, regular_user, grant_page, tree):
        """Same content, other URLs. Deciding it twice is how they diverge."""
        user = grant_page(regular_user, tree["marketing"], "change")
        legal = tree["legal"].pk
        assert raw_client.get(f"/cms/v1/pages/{legal}/body/", user=user).status_code == 404
        assert raw_client.get(f"/cms/v1/pages/{legal}/blocks/whatever/", user=user).status_code == 404
        assert raw_client.get(f"/cms/v1/pages/{tree['marketing'].pk}/body/", user=user).status_code == 200


class TestTheAncestorIsNotReadable:
    """The decision this commit turns on.

    ``explorable_instances`` would include Home — Wagtail adds the ancestors
    of every granted page so the admin tree can be walked down to your
    subtree. These endpoints serve draft content rather than a navigation
    tree, so they use the permission set instead.
    """

    def test_wagtail_would_have_offered_the_ancestor(self, db, regular_user, grant_page, tree):
        """Pinned so the two sets cannot quietly converge and hide the choice."""
        from wagtail.permissions import page_permission_policy as policy

        user = grant_page(regular_user, tree["marketing"], "change")
        explorable = {p.pk for p in policy.explorable_instances(user)}
        assert tree["home"].pk in explorable, "if this fails, Wagtail changed and the reasoning needs rechecking"
        assert tree["home"].permissions_for_user(user).can_edit() is False

    def test_but_the_api_does_not(self, raw_client, regular_user, grant_page, tree):
        user = grant_page(regular_user, tree["marketing"], "change")
        assert raw_client.get(f"/cms/v1/pages/{tree['home'].pk}/", user=user).status_code == 404

    def test_nor_its_draft_body(self, raw_client, regular_user, grant_page, tree):
        """The sharpest version: the ancestor's unreviewed edits."""
        user = grant_page(regular_user, tree["marketing"], "change")
        assert raw_client.get(f"/cms/v1/pages/{tree['home'].pk}/body/", user=user).status_code == 404


class TestTheParentFilterDoesNotLeak:
    """Narrowing the results is not enough if a filter resolves outside them."""

    def test_filtering_by_an_unreadable_parent_reveals_nothing(self, raw_client, regular_user, grant_page, tree):
        user = grant_page(regular_user, tree["marketing"], "change")
        unreadable = raw_client.get(f"/cms/v1/pages/?parent={tree['legal'].pk}", user=user)
        missing = raw_client.get("/cms/v1/pages/?parent=999999", user=user)
        assert unreadable.status_code == missing.status_code, "a real page answers differently from an absent one"

    def test_filtering_by_a_readable_parent_still_works(self, raw_client, regular_user, grant_page, tree):
        user = grant_page(regular_user, tree["marketing"], "change")
        body = raw_client.get(f"/cms/v1/pages/?parent={tree['marketing'].pk}", user=user).json()
        assert {p["title"] for p in body["pages"]} == {"Campaigns"}


class TestWritesStillAskTheTester:
    """These were already object-checked. The scopes must not have widened them."""

    def test_editing_in_the_subtree_is_allowed(self, raw_client, regular_user, grant_page, tree):
        user = grant_page(regular_user, tree["marketing"], "change")
        response = raw_client.patch(
            f"/cms/v1/pages/{tree['campaigns'].pk}/",
            json={"title": "Campaigns 2026"},
            headers={"If-Match": "*"},
            user=user,
        )
        assert response.status_code == 200, response.json()

    def test_editing_a_sibling_subtree_is_refused(self, raw_client, regular_user, grant_page, tree):
        user = grant_page(regular_user, tree["marketing"], "change")
        response = raw_client.patch(
            f"/cms/v1/pages/{tree['legal'].pk}/",
            json={"title": "Nope"},
            headers={"If-Match": "*"},
            user=user,
        )
        assert response.status_code == 403

    def test_changing_does_not_grant_publishing(self, raw_client, regular_user, grant_page, tree):
        """Wagtail's can_publish asks for publish and nothing else."""
        user = grant_page(regular_user, tree["marketing"], "change")
        response = raw_client.post(
            f"/cms/v1/pages/{tree['campaigns'].pk}/publish/",
            json={},
            headers={"If-Match": "*"},
            user=user,
        )
        assert response.status_code == 403

    def test_publishing_with_the_grant_is_allowed(self, raw_client, regular_user, grant_page, tree):
        user = grant_page(regular_user, tree["marketing"], "change", "publish")
        assert user.has_perm("wagtailcore.publish_page") is False
        tree["campaigns"].specific.save_revision()
        response = raw_client.post(
            f"/cms/v1/pages/{tree['campaigns'].pk}/publish/",
            json={},
            headers={"If-Match": "*"},
            user=user,
        )
        assert response.status_code == 200, response.json()


class TestTheCredentialHalf:
    def test_a_read_token_reads_but_does_not_write(self, raw_client, regular_user, grant_page, tree, scoped_token):
        user = grant_page(regular_user, tree["marketing"], "change")
        headers = scoped_token(user, "wagtailcore.view_page")

        assert raw_client.get(f"/cms/v1/pages/{tree['marketing'].pk}/", headers=headers).status_code == 200

        response = raw_client.patch(
            f"/cms/v1/pages/{tree['marketing'].pk}/",
            json={"title": "Nope"},
            headers={**headers, "If-Match": "*"},
        )
        assert response.status_code == 403
        assert "scopes" in response.json()["detail"]

    def test_a_token_alone_grants_no_page(self, raw_client, regular_user, tree, scoped_token):
        """Minting does not require holding what it names."""
        headers = scoped_token(regular_user, "wagtailcore.view_page")
        assert raw_client.get(f"/cms/v1/pages/{tree['marketing'].pk}/", headers=headers).status_code == 404


class TestTheWagtailSeamsWeDependOn:
    """Tripwires for a Wagtail upgrade, not assertions about our code."""

    def test_the_six_actions_are_still_the_six(self, db):
        from phoxtail.cms.api.v1._permissions import page_actions

        assert page_actions() == {"add", "bulk_delete", "change", "lock", "publish", "unlock"}

    def test_wagtail_still_references_no_view_page_permission(self, db):
        """If it grows one, reading should ask for it rather than narrow.

        ``wagtailcore.view_page`` is named by the read endpoints as a label
        for the token half only; the person half is the narrowing. That is
        only honest while Wagtail itself ignores the codename.
        """
        from phoxtail.cms.api.v1._permissions import page_actions

        assert "view" not in page_actions()
