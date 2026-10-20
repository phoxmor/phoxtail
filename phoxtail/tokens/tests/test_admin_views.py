"""The API Tokens admin: core's list, drawers and the action cycle."""

import json

import pytest
from django.contrib.messages.storage.cookie import CookieStorage
from django.test import RequestFactory
from django.urls import reverse
from django_htmx.middleware import HtmxDetails

from phoxtail.tokens.models import AccessToken

from .conftest import grant_token_permissions
from .factories import AccessTokenFactory

# The name a change to a token goes out under (core's change_event): pinned,
# so a rename fails here.
TOKEN_CHANGED = "phoxtail_tokens.accesstoken:changed"

pytestmark = [pytest.mark.django_db, pytest.mark.urls("phoxtail.tokens.tests.admin_urls")]


def _views():
    # Deferred: the views import phoxtail.tokens.filters, whose module-level
    # get_search_backend() touches the database (test_admin_utils.py).
    from phoxtail.tokens.admin import views

    return views


def url(name, *args):
    return reverse(f"access_tokens_management:{name}", args=args)


def call(view, person, method="get", data=None, htmx=True, **kwargs):
    factory = RequestFactory()
    headers = {"HTTP_HX_REQUEST": "true"} if htmx else {}
    request = getattr(factory, method)("/", data or {}, **headers)
    request.user = person
    request.htmx = HtmxDetails(request)
    request._messages = CookieStorage(request)
    return getattr(_views(), view)(request, **kwargs)


class TestList:
    def test_the_page_stands_on_the_ground_and_redraws_on_a_change(self, superuser):
        html = call("admin_tokens_list_view", superuser, htmx=False).content.decode()

        assert "phx-ground" in html
        assert f'hx-trigger="{TOKEN_CHANGED} from:body"' in html
        assert "tka-" not in html

    def test_an_htmx_request_answers_the_list_alone(self, superuser):
        AccessTokenFactory(user=superuser, name="Laptop")
        html = call("admin_tokens_list_view", superuser).content.decode()

        assert "Laptop" in html
        assert "<html" not in html


class TestFilters:
    def test_the_footer_counts_the_matches(self, superuser):
        AccessTokenFactory.create_batch(2, user=superuser)
        html = call("admin_tokens_filters_form_view", superuser).content.decode()

        assert "Show 2 tokens" in html

    def test_only_the_viewers_own_tokens_are_counted(self, user, other_user):
        AccessTokenFactory(user=user)
        AccessTokenFactory.create_batch(3, user=other_user)
        person = grant_token_permissions(user, "access_tokens_management")
        html = call("admin_tokens_filters_form_view", person).content.decode()

        assert "Show 1 token" in html


class TestCreate:
    def test_a_create_shows_the_token_once_in_place_of_the_drawer(self, superuser):
        response = call("admin_token_create_view", superuser, "post", {"name": "CLI", "unrestricted": "on"})
        html = response.content.decode()

        assert response.status_code == 200
        assert response["HX-Retarget"] == "closest [data-modal-content]"
        assert response["HX-Reswap"].startswith("innerHTML swap:")
        assert json.loads(response["HX-Trigger"]) == {TOKEN_CHANGED: {}}
        assert "no-store" in response["Cache-Control"]
        assert '<h2 class="phoxtail-drawer__title">CLI</h2>' in html
        assert 'value="phxt_' in html
        # Hidden until its eye shows it; copied either way.
        assert 'type="password"' in html
        assert "data-password-toggle" in html
        assert "data-copy" in html
        # Its one button copies and closes; nothing else in the footer.
        assert "Copy and close" in html
        assert "Close</span>" not in html
        # A dialog in the center that a stray click or Escape cannot close.
        assert 'data-modal-side="center"' in html
        assert 'data-modal-dismiss="button"' in html

    def test_a_refused_create_redraws_its_fields(self, superuser):
        response = call("admin_token_create_view", superuser, "post", {"name": ""})
        html = response.content.decode()

        assert response.status_code == 200
        assert "HX-Retarget" not in response
        assert 'hx-swap-oob="innerHTML:#create-token-form"' in html
        assert not AccessToken.objects.exists()


class TestDetail:
    def test_an_active_token_offers_revoke(self, superuser):
        token = AccessTokenFactory(user=superuser)
        html = call("admin_token_detail_form_view", superuser, token_id=token.uuid).content.decode()

        assert url("admin_token_revoke", token.uuid) in html

    def test_a_revoked_token_does_not(self, superuser):
        token = AccessTokenFactory(user=superuser)
        call("admin_token_revoke_view", superuser, "post", token_id=token.uuid)
        html = call("admin_token_detail_form_view", superuser, token_id=token.uuid).content.decode()

        assert url("admin_token_revoke", token.uuid) not in html
        assert "Revoked" in html


class TestRevoke:
    def test_a_revoke_closes_the_drawer_and_the_list_redraws(self, superuser):
        token = AccessTokenFactory(user=superuser, name="Old")
        response = call("admin_token_revoke_view", superuser, "post", token_id=token.uuid)

        assert response.status_code == 204
        assert json.loads(response["HX-Trigger"]) == {
            TOKEN_CHANGED: {},
            "closeModal": {},
            "showToast": {"message": "Token 'Old' revoked.", "type": "success"},
        }
        token.refresh_from_db()
        assert token.revoked_at is not None
