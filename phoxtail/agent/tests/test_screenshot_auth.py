"""The screenshot view's query-parameter authentication.

Playwright cannot set request headers while navigating, so this one view
accepts ``?token=`` instead of an Authorization header. That makes it the
only place outside the Ninja adapter that consumes
``phoxtail.tokens.auth.authenticate`` directly — and therefore the only
place a change to what that function returns can go wrong unnoticed.

It nearly did: ``authenticate`` now resolves an ``AccessToken`` rather
than a ``User``, and ``AccessToken`` happens to expose ``is_active``. A
permission policy checking ``is_active`` first would pass that check on
the wrong object and fail only on the next attribute — a late, confusing
failure instead of an immediate one. These tests pin the contract so the
next change to that seam breaks loudly.
"""

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType

from phoxtail.agent.permissions.models import AgentAdminPermission
from phoxtail.agent.views import _authenticate_screenshot_request
from phoxtail.tokens.tests.factories import AccessTokenFactory, UserFactory

User = get_user_model()
pytestmark = pytest.mark.django_db


def _request(rf, token: str | None):
    return rf.get("/screenshot/", {"token": token} if token is not None else {})


def _with_chatbot_access(user):
    ct = ContentType.objects.get_for_model(AgentAdminPermission)
    perm = Permission.objects.get(content_type=ct, codename="access_chatbot")
    user.user_permissions.add(perm)
    # has_perm results are cached on the instance; re-fetch to see the grant.
    return User.objects.get(pk=user.pk)


class TestScreenshotAuthentication:
    def test_returns_the_user_not_the_token(self, rf):
        """The view's callers expect a person. Returning the credential
        would put an AccessToken where a User is used."""
        user = _with_chatbot_access(UserFactory())
        token = AccessTokenFactory(user=user)

        result = _authenticate_screenshot_request(_request(rf, token._raw_token))

        assert result == user
        assert isinstance(result, User)

    def test_refuses_a_valid_token_whose_user_lacks_chatbot_access(self, rf):
        """Authenticated is not authorized. This is the assertion that
        catches a permission check accidentally run against the token."""
        token = AccessTokenFactory(user=UserFactory())
        assert _authenticate_screenshot_request(_request(rf, token._raw_token)) is None

    def test_refuses_an_unknown_token(self, rf):
        assert _authenticate_screenshot_request(_request(rf, "phxt_zzznosuchtokennosuchtoken")) is None

    def test_refuses_a_missing_token(self, rf):
        assert _authenticate_screenshot_request(_request(rf, None)) is None

    def test_refuses_a_revoked_token(self, rf):
        from django.utils import timezone

        user = _with_chatbot_access(UserFactory())
        token = AccessTokenFactory(user=user, revoked_at=timezone.now())
        assert _authenticate_screenshot_request(_request(rf, token._raw_token)) is None


class TestWhichPagesTheCameraMaySee:
    """``access_chatbot`` says you may drive the renderer, not what it points at.

    Until now that was the only question asked. The view then called
    ``resolve_page_for_read(page_id)`` with no page check at all — and
    Wagtail grants pages per subtree, so anyone holding chatbot access could
    photograph any page by id, including an unpublished draft in a subtree
    they were never granted. ``page_id`` is a plain integer, so nothing
    stopped that being swept: unlike the block screenshot, which at least
    needs a uuid, the viewport screenshot needs only a number.

    The gate is now the one ``GET /cms/v1/pages/{id}/`` uses, because this
    renders the same draft.

    The views are called directly rather than over the test client: the
    agent URLconf is not mounted in the test settings, and these tests are
    about the views' own decision rather than their routing.
    """

    @pytest.fixture
    def tree(self, db):
        from wagtail.models import Page

        from phoxtail.cms.models import SitePage

        home = Page.objects.get(depth=2)
        marketing = home.add_child(instance=SitePage(title="Marketing", slug="marketing"))
        legal = home.add_child(instance=SitePage(title="Legal", slug="legal"))
        return {"home": home, "marketing": marketing, "legal": legal}

    @staticmethod
    def _grant_page(user, page, action):
        from django.contrib.auth.models import Group
        from wagtail.models import GroupPagePermission

        group, _ = Group.objects.get_or_create(name="screenshot-grantees")
        user.groups.add(group)
        GroupPagePermission.objects.create(
            group=group,
            page=page,
            permission=Permission.objects.get(content_type__app_label="wagtailcore", codename=f"{action}_page"),
        )
        return User.objects.get(pk=user.pk)

    @staticmethod
    def _shoot(rf, token, page_id, block_uuid=None):
        from phoxtail.agent.views import (
            render_page_for_screenshot,
            render_page_for_viewport_screenshot,
        )

        request = rf.get("/screenshot/", {"token": token._raw_token})
        if block_uuid is None:
            return render_page_for_viewport_screenshot(request, page_id)
        return render_page_for_screenshot(request, page_id, block_uuid)

    def test_a_page_outside_the_grant_is_404(self, rf, tree):
        user = self._grant_page(_with_chatbot_access(UserFactory()), tree["marketing"], "change")
        token = AccessTokenFactory(user=user)
        assert self._shoot(rf, token, tree["legal"].pk).status_code == 404

    def test_chatbot_access_alone_photographs_nothing(self, rf, tree):
        """The escalation itself: the permission that used to be enough."""
        token = AccessTokenFactory(user=_with_chatbot_access(UserFactory()))
        assert self._shoot(rf, token, tree["marketing"].pk).status_code == 404

    def test_the_block_screenshot_is_gated_too(self, rf, tree):
        """Both views call the same resolver, so both need the same gate."""
        token = AccessTokenFactory(user=_with_chatbot_access(UserFactory()))
        assert self._shoot(rf, token, tree["legal"].pk, "some-uuid").status_code == 404

    def test_no_chatbot_access_is_still_403_not_404(self, rf, tree):
        """The two refusals stay distinct: bad credential, or wrong page."""
        token = AccessTokenFactory(user=UserFactory())
        assert self._shoot(rf, token, tree["marketing"].pk).status_code == 403

    def test_a_granted_page_passes_the_gate(self, rf, tree):
        """Asked of the gate itself — rendering the page needs site context
        this test has no business assembling."""
        from phoxtail.agent.views import _may_read_page

        user = self._grant_page(_with_chatbot_access(UserFactory()), tree["marketing"], "change")
        assert _may_read_page(user, tree["marketing"]) is True
        assert _may_read_page(user, tree["legal"]) is False
        assert user.has_perm("wagtailcore.change_page") is False
