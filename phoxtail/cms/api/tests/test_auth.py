"""What each cms endpoint asks of its caller.

``page-types`` asks for nothing, and the interesting part is that saying so
takes an annotation rather than silence. ``sites`` and ``locales`` do name
codenames, and are covered here because Wagtail grants both globally — so
``guarded()`` is the whole answer and the check belongs at the door. The three
object-level families each carry their own tests, because a global check
cannot express what they actually decide.

Sites and locales are verified rather than assumed to be global: pages,
collections and the per-site settings all turned out not to be.

One set per codename rather than per endpoint. Whether an endpoint was missed
is a different question, answered by ``tests/test_tool_scopes.py``.

``TestNarrowedTokens`` is the part worth copying forward. Every per-domain
auth test in this workstream authenticates through ``PhoxtailSessionAuth``,
where ``token`` is ``None`` and the credential half of the question is
answered "no ceiling" before it is really asked. That makes a session test
blind to whether a *narrowed* credential can reach an endpoint at all — which
is how a door shut to every scoped token in the project passed a full suite.
"""

from __future__ import annotations


def test_unauthenticated_request_is_401(db, raw_client):
    """No caller at all is a different event from the wrong caller."""
    assert raw_client.get("/cms/v1/sites/").status_code == 401


class TestSites:
    """Wagtail grants site permissions globally — proven, not assumed."""

    def test_the_policy_really_is_global(self, db):
        from wagtail.permission_policies.base import ModelPermissionPolicy
        from wagtail.permissions import site_permission_policy

        assert type(site_permission_policy) is ModelPermissionPolicy

    def test_listing_without_the_permission_is_403(self, raw_client, regular_user):
        """The hole this closes: listing every site used to need nothing."""
        response = raw_client.get("/cms/v1/sites/", user=regular_user)
        assert response.status_code == 403
        assert "view_site" in response.json()["detail"]

    def test_reading_one_site_without_the_permission_is_403(self, raw_client, regular_user, site):
        response = raw_client.get(f"/cms/v1/sites/{site.pk}/", user=regular_user)
        assert response.status_code == 403
        assert "view_site" in response.json()["detail"]

    def test_reading_with_the_permission_is_allowed(self, raw_client, regular_user, grant, site):
        """The widening this commit is for: no superuser flag involved."""
        user = grant(regular_user, "wagtailcore", "view_site")
        assert raw_client.get("/cms/v1/sites/", user=user).status_code == 200
        assert raw_client.get(f"/cms/v1/sites/{site.pk}/", user=user).status_code == 200

    def test_reading_does_not_grant_creating(self, raw_client, regular_user, grant, site):
        user = grant(regular_user, "wagtailcore", "view_site")
        response = raw_client.post(
            "/cms/v1/sites/",
            json={
                "hostname": "new.example.invalid",
                "port": 80,
                "site_name": "New",
                "root_page_id": site.root_page_id,
                "is_default_site": False,
            },
            user=user,
        )
        assert response.status_code == 403
        assert "add_site" in response.json()["detail"]

    def test_changing_does_not_grant_deleting(self, raw_client, regular_user, grant, site):
        user = grant(regular_user, "wagtailcore", "change_site")
        response = raw_client.delete(
            f"/cms/v1/sites/{site.pk}/",
            headers={"If-Match": "*"},
            user=user,
        )
        assert response.status_code == 403
        assert "delete_site" in response.json()["detail"]

    def test_creating_does_not_grant_changing(self, raw_client, regular_user, grant, site):
        user = grant(regular_user, "wagtailcore", "add_site")
        response = raw_client.patch(
            f"/cms/v1/sites/{site.pk}/",
            json={"site_name": "Renamed"},
            headers={"If-Match": "*"},
            user=user,
        )
        assert response.status_code == 403
        assert "change_site" in response.json()["detail"]

    def test_an_unknown_site_answers_403_not_404(self, raw_client, regular_user):
        """Reading now refuses before it resolves, so ids cannot be swept.

        This inverts what the endpoint used to do — ``_resolve_site`` raised
        404 for an unknown id, and a caller with no grant could tell a real
        site from an imaginary one by asking. Media answers the same threat
        the opposite way round, hiding reads behind 404, because there the
        grant is per collection and there is a "files you may see" set to
        resolve within. Sites are granted globally: either you may read them
        all or none, so there is no narrowed set and 403 at the door is the
        only answer available.
        """
        assert raw_client.get("/cms/v1/sites/999999/", user=regular_user).status_code == 403

    def test_the_permission_check_runs_before_the_etag_check(self, raw_client, regular_user, site):
        """A caller with no rights learns nothing about the current state.

        ``guarded()`` runs at the door, so a missing or stale If-Match never
        gets the chance to answer 428 or 412 and confirm the site exists.
        """
        assert raw_client.delete(f"/cms/v1/sites/{site.pk}/", user=regular_user).status_code == 403

    def test_superuser_is_still_admitted(self, client, site):
        assert client.get("/cms/v1/sites/").status_code == 200


class TestLocales:
    """A catalogue backed by rows, so it is gated by the grant over them."""

    def test_listing_without_the_permission_is_403(self, raw_client, regular_user):
        response = raw_client.get("/cms/v1/locales/", user=regular_user)
        assert response.status_code == 403
        assert "view_locale" in response.json()["detail"]

    def test_listing_with_the_permission_is_allowed(self, raw_client, regular_user, grant):
        user = grant(regular_user, "wagtailcore", "view_locale")
        assert raw_client.get("/cms/v1/locales/", user=user).status_code == 200

    def test_a_site_grant_does_not_open_locales(self, raw_client, regular_user, grant):
        """Two catalogues, two grants — the mistake a copy-paste pass makes."""
        user = grant(regular_user, "wagtailcore", "view_site")
        assert raw_client.get("/cms/v1/locales/", user=user).status_code == 403


class TestPageTypes:
    """Deliberately open — and open to narrowed tokens too, which is the part
    that does not come for free."""

    def test_any_authenticated_caller_may_read_the_catalogue(self, raw_client, regular_user):
        """It lists page type and field *names* from installed code.

        No rows, no content, and no permission naming it. An agent reads it
        before it can phrase a request at all; the content behind those types
        is a separate question the pages endpoints answer per subtree.
        """
        assert raw_client.get("/cms/v1/page-types/", user=regular_user).status_code == 200

    def test_it_is_still_closed_to_nobody(self, db, raw_client):
        """``authenticated()`` is not ``auth=None`` — anonymous is still 401."""
        assert raw_client.get("/cms/v1/page-types/").status_code == 401

    def test_a_narrowed_token_can_still_read_it(self, raw_client, regular_user, scoped_token):
        """The reason it carries ``authenticated()`` instead of nothing.

        A token minted to let an agent create pages must be able to read the
        field list first, or the workflow dies at its discovery step. Left
        bare, this endpoint would keep the API-wide default and refuse every
        narrowed credential in the project — while every session-based test
        beside it carried on passing.
        """
        headers = scoped_token(regular_user, "wagtailcore.add_page")
        assert raw_client.get("/cms/v1/page-types/", headers=headers).status_code == 200

    def test_a_token_narrowed_to_something_unrelated_can_read_it_too(self, raw_client, regular_user, scoped_token):
        """There is no codename behind this, so no token is the wrong token."""
        headers = scoped_token(regular_user, "phoxtail_streams.view_block")
        assert raw_client.get("/cms/v1/page-types/", headers=headers).status_code == 200

    def test_the_tool_that_calls_it_names_nothing_either(self):
        """Both halves agree, so a narrowed token is neither lied to nor
        withheld from.

        The two defaults are opposites — an endpoint naming nothing is closed
        to scoped tokens, a tool naming nothing is offered to all — so the
        pair only tells the truth when the endpoint says "open" out loud.
        """
        from phoxtail.cms.mcp import resources

        assert getattr(resources.page_types_list, "auth", None) in (None, [])


class TestNarrowedTokens:
    """That the fixture mints something genuinely narrowed.

    Without this the tests above would pass with a fixture that quietly
    handed back an unrestricted token, which is exactly the failure mode
    they exist to rule out.
    """

    def test_the_minted_token_really_carries_a_ceiling(self, db, regular_user, scoped_token):
        from phoxtail.api.auth import has_no_ceiling
        from phoxtail.core.authorization import AuthorizationContext
        from phoxtail.tokens.models import AccessToken

        scoped_token(regular_user, "wagtailcore.add_page")
        token = AccessToken.objects.filter(user=regular_user).latest("created_at")
        assert token.unrestricted is False
        assert token.scopes == ["wagtailcore.add_page"]
        assert has_no_ceiling(AuthorizationContext(user=regular_user, token=token)) is False

    def test_the_named_scope_opens_a_guarded_door(self, raw_client, regular_user, grant, scoped_token):
        """Both halves pass: the person holds it and the token names it."""
        user = grant(regular_user, "wagtailcore", "view_locale")
        headers = scoped_token(user, "wagtailcore.view_locale")
        assert raw_client.get("/cms/v1/locales/", headers=headers).status_code == 200

    def test_a_different_scope_does_not(self, raw_client, regular_user, grant, scoped_token):
        """Holding the permission is not enough if the token was not minted
        for it — the two halves are asked separately and both must pass."""
        user = grant(regular_user, "wagtailcore", "view_locale")
        headers = scoped_token(user, "wagtailcore.view_site")
        response = raw_client.get("/cms/v1/locales/", headers=headers)
        assert response.status_code == 403
        assert "scopes" in response.json()["detail"]

    def test_the_scope_alone_does_not_grant_the_permission(self, raw_client, regular_user, scoped_token):
        """A scope can only ever subtract. Minting does not require holding
        what it names, so a token naming a codename must not confer it."""
        headers = scoped_token(regular_user, "wagtailcore.view_locale")
        response = raw_client.get("/cms/v1/locales/", headers=headers)
        assert response.status_code == 403
        assert "does not have permission" in response.json()["detail"]

    def test_an_endpoint_naming_another_codename_refuses_it(self, raw_client, regular_user, scoped_token):
        """The contrast that makes ``page-types`` worth testing.

        ``/collections/`` names ``view_collection``, which this token was not
        minted for, so it is refused where ``page-types`` is not. What an
        endpoint naming nothing does is covered in ``api/tests/test_default.py``.
        """
        headers = scoped_token(regular_user, "wagtailcore.add_page")
        assert raw_client.get("/cms/v1/collections/", headers=headers).status_code == 403
