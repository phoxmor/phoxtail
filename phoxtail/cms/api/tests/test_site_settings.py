"""What the site-settings, font and palette endpoints ask of their caller.

**Wagtail 8 grants settings per site**, through ``GroupSitePermission`` rows
and ``SitePermissionPolicy``. So ``guarded()`` would have been wrong here for
the same reason it was wrong for collections — ``has_perm`` answers False for
someone the admin has genuinely granted — and this is the correction that the
earlier, reverted cms attempt would have shipped as a regression.

Two things that look odd and are both copied rather than chosen:

* **Reading asks for ``change``.** Wagtail's settings surface names exactly
  one action; a grep of ``wagtail/contrib/settings`` finds no reference to a
  view action at all, because there is no read-only settings view. Reading is
  what changing permits.
* **The children name their parent's codename.** ``SiteSettingFont`` and
  ``SiteSettingPalette`` are ``ParentalKey`` children edited through
  ``InlinePanel`` inside ``SiteSetting``'s own form. They have their own
  permission rows, because Django creates them, but nothing checks those rows
  — so naming them would invent an authority the admin cannot express.
"""

from __future__ import annotations

import pytest


@pytest.fixture
def other_site(db, site):
    """A second site, so a per-site grant can be shown not to reach it."""
    from wagtail.models import Site

    return Site.objects.create(
        hostname="other.example.invalid",
        port=80,
        site_name="Other",
        root_page=site.root_page,
        is_default_site=False,
    )


@pytest.fixture
def grant_site():
    """Grant a settings action on one site, Wagtail's way."""
    from django.contrib.auth.models import Group, Permission
    from wagtail.permission_policies.sites import GroupSitePermission

    def _grant(user, site, codename="change_sitesetting"):
        group, _ = Group.objects.get_or_create(name="site-settings-grantees")
        user.groups.add(group)
        GroupSitePermission.objects.create(
            group=group,
            site=site,
            permission=Permission.objects.get(content_type__app_label="phoxtail_cms", codename=codename),
        )
        return type(user).objects.get(pk=user.pk)

    return _grant


PATHS = [
    "/cms/v1/site-settings/{site_id}/",
    "/cms/v1/site-settings/{site_id}/fonts/",
    "/cms/v1/site-settings/{site_id}/palettes/",
]


class TestTheGrantIsPerSite:
    """The correction. A per-site grantee is admitted; has_perm says no."""

    @pytest.mark.parametrize("path", PATHS)
    def test_a_per_site_grantee_is_admitted(self, raw_client, regular_user, grant_site, site, path):
        user = grant_site(regular_user, site)
        assert user.has_perm("phoxtail_cms.change_sitesetting") is False, "guarded() would have refused this user"
        assert raw_client.get(path.format(site_id=site.pk), user=user).status_code == 200

    @pytest.mark.parametrize("path", PATHS)
    def test_the_grant_does_not_reach_another_site(self, raw_client, regular_user, grant_site, site, other_site, path):
        """Per-site means per-site. A test granting on one site and reading
        that same site cannot tell a scoped grant from a blanket one."""
        user = grant_site(regular_user, site)
        assert raw_client.get(path.format(site_id=other_site.pk), user=user).status_code == 403

    @pytest.mark.parametrize("path", PATHS)
    def test_no_grant_at_all_is_refused(self, raw_client, regular_user, site, path):
        response = raw_client.get(path.format(site_id=site.pk), user=regular_user)
        assert response.status_code == 403
        assert "settings for that site" in response.json()["detail"]

    def test_a_global_grant_still_works(self, raw_client, regular_user, grant, site):
        """The policy ORs global permissions with per-site rows, so the
        people who could reach these endpoints before still can."""
        user = grant(regular_user, "phoxtail_cms", "change_sitesetting")
        assert raw_client.get(f"/cms/v1/site-settings/{site.pk}/", user=user).status_code == 200

    def test_superuser_is_still_admitted(self, client, site):
        assert client.get(f"/cms/v1/site-settings/{site.pk}/").status_code == 200


class TestWritingIsGuardedToo:
    def test_patching_settings_without_a_grant_is_refused(self, raw_client, regular_user, site):
        response = raw_client.patch(
            f"/cms/v1/site-settings/{site.pk}/",
            json={"logo_id": None},
            headers={"If-Match": "*"},
            user=regular_user,
        )
        assert response.status_code == 403

    def test_the_permission_check_runs_before_the_etag_check(self, raw_client, regular_user, site):
        """No If-Match at all would be 428; the refusal comes first, so a
        caller with no grant learns nothing about the current state."""
        response = raw_client.patch(f"/cms/v1/site-settings/{site.pk}/", json={"logo_id": None}, user=regular_user)
        assert response.status_code == 403

    def test_adding_a_font_without_a_grant_is_refused(self, raw_client, regular_user, site):
        response = raw_client.post(
            f"/cms/v1/site-settings/{site.pk}/fonts/",
            json={"font_family_id": 1, "role_id": 1},
            user=regular_user,
        )
        assert response.status_code == 403

    def test_a_per_site_grantee_may_add_a_font(self, raw_client, regular_user, grant_site, site, db):
        from phoxtail.design.models import FontFamily, FontRole

        family = FontFamily.objects.create(name="Inter")
        role = FontRole.objects.create(name="Body", identifier="body", description="running text")
        user = grant_site(regular_user, site)
        response = raw_client.post(
            f"/cms/v1/site-settings/{site.pk}/fonts/",
            json={"font_family_id": family.pk, "role_id": role.pk},
            user=user,
        )
        assert response.status_code == 201, response.json()


class TestTheChildrenNameTheirParent:
    """The decision taken with the user, stated where it can be checked."""

    def test_a_child_permission_grants_nothing(self, raw_client, regular_user, grant, site):
        """change_sitesettingfont is a real row that nothing checks.

        Granting it must not open the font endpoints, or the API would be
        honouring an authority the Wagtail admin has no way to express.
        """
        user = grant(regular_user, "phoxtail_cms", "change_sitesettingfont")
        assert raw_client.get(f"/cms/v1/site-settings/{site.pk}/fonts/", user=user).status_code == 403

    def test_the_parent_permission_opens_the_children(self, raw_client, regular_user, grant_site, site):
        user = grant_site(regular_user, site)
        assert raw_client.get(f"/cms/v1/site-settings/{site.pk}/fonts/", user=user).status_code == 200
        assert raw_client.get(f"/cms/v1/site-settings/{site.pk}/palettes/", user=user).status_code == 200


class TestTheWagtailSeamsWeDependOn:
    """Tripwires for a Wagtail upgrade, not assertions about our code."""

    def test_the_policy_is_still_the_per_site_one(self, db):
        from wagtail.permission_policies.sites import SitePermissionPolicy

        from phoxtail.cms.api.v1._permissions import settings_policy

        assert isinstance(settings_policy(), SitePermissionPolicy)

    def test_wagtail_still_asks_only_for_change(self, db):
        """If a read action ever appears, reading should ask for it instead."""
        from wagtail.contrib.settings.views import EditView

        from phoxtail.cms.api.v1._permissions import SETTINGS_ACTION

        assert EditView.permission_required == SETTINGS_ACTION


class TestTheCredentialHalf:
    def test_a_read_token_reads_but_does_not_write(self, raw_client, regular_user, grant_site, site, scoped_token):
        """The narrowing the read codename exists for.

        The person's half is ``change`` either way, because Wagtail has no
        read action — but the token can still be minted read-only, and that
        is a real capability rather than a spelling.
        """
        user = grant_site(regular_user, site)
        headers = scoped_token(user, "phoxtail_cms.view_sitesetting")

        assert raw_client.get(f"/cms/v1/site-settings/{site.pk}/", headers=headers).status_code == 200

        response = raw_client.patch(
            f"/cms/v1/site-settings/{site.pk}/",
            json={"logo_id": None},
            headers={**headers, "If-Match": "*"},
        )
        assert response.status_code == 403
        assert "scopes" in response.json()["detail"]

    def test_a_write_token_with_no_grant_is_still_refused(self, raw_client, regular_user, site, scoped_token):
        headers = scoped_token(regular_user, "phoxtail_cms.change_sitesetting")
        response = raw_client.patch(
            f"/cms/v1/site-settings/{site.pk}/",
            json={"logo_id": None},
            headers={**headers, "If-Match": "*"},
        )
        assert response.status_code == 403
        assert "settings for that site" in response.json()["detail"]
