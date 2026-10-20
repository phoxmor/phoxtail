"""The Remotes admin: core's list, drawers and the action cycle."""

import json
from unittest import mock

import httpx
import pytest
from django.contrib.auth import get_user_model
from django.contrib.messages.storage.cookie import CookieStorage
from django.test import RequestFactory
from django_htmx.middleware import HtmxDetails

from phoxtail.remotes.admin.remotes import views
from phoxtail.remotes.models import Remote

# The name a change to a remote goes out under (core's change_event): pinned,
# so a rename fails here.
REMOTE_CHANGED = "phoxtail_remotes.remote:changed"

pytestmark = [pytest.mark.django_db, pytest.mark.urls("phoxtail.remotes.tests.admin_urls")]


@pytest.fixture
def admin():
    return get_user_model().objects.create_superuser(username="lab-admin", email="admin@example.com", password="x")


@pytest.fixture
def registry():
    return Remote.objects.create(name="Registry", base_url="https://registry.example.com", token="secret-token-1234")


def call(view, person, method="get", data=None, htmx=True, **kwargs):
    headers = {"HTTP_HX_REQUEST": "true"} if htmx else {}
    request = getattr(RequestFactory(), method)("/", data or {}, **headers)
    request.user = person
    request.htmx = HtmxDetails(request)
    request._messages = CookieStorage(request)
    response = getattr(views, view)(request, **kwargs)
    response.messages = [str(m) for m in request._messages._queued_messages]
    return response


def events(response):
    return json.loads(response["HX-Trigger"])


class TestList:
    def test_the_page_stands_on_the_ground_and_redraws_on_a_change(self, admin):
        html = call("admin_remotes_index", admin, htmx=False).content.decode()

        assert "phx-ground" in html
        assert f'hx-trigger="{REMOTE_CHANGED} from:body"' in html
        assert "rga-" not in html

    def test_an_htmx_request_answers_the_list_alone(self, admin, registry):
        html = call("admin_remotes_index", admin).content.decode()

        assert "Registry" in html
        assert "<html" not in html

    def test_a_search_redraws_the_list_out_of_band(self, admin, registry):
        Remote.objects.create(name="Staging", base_url="https://staging.example.com", token="t")
        html = call("admin_remotes_search", admin, data={"filter-search": "Staging"}).content.decode()

        assert 'hx-swap-oob="innerHTML:#remotes-container"' in html
        assert "Staging" in html
        assert "Registry" not in html

    def test_a_redraw_keeps_the_page_it_was_on(self, admin):
        for n in range(views.PAGE_SIZE + 1):
            Remote.objects.create(name=f"Remote {n:02}", base_url=f"https://r{n}.example.com", token="t")
        html = call("admin_remotes_index", admin, data={"filter-page": "2"}).content.decode()

        assert f"Remote {views.PAGE_SIZE:02}" in html
        assert 'name="filter-page" value="2"' in html

    def test_an_empty_list_says_so_without_an_icon(self, admin):
        html = call("admin_remotes_index", admin).content.decode()

        assert "No remotes connected" in html


class TestConnect:
    def _ping(self, status=200):
        return mock.patch.object(httpx, "get", return_value=httpx.Response(status, request=httpx.Request("GET", "x")))

    def test_a_connect_announces_the_change_and_closes(self, admin):
        with self._ping():
            response = call(
                "admin_remote_add",
                admin,
                "post",
                {"name": "Peer", "base_url": "https://peer.example.com/", "token": "abc"},
            )

        assert response.status_code == 204
        assert {REMOTE_CHANGED, "closeModal", "showToast"} <= events(response).keys()
        assert Remote.objects.get(name="Peer").base_url == "https://peer.example.com"

    def test_a_refused_connect_redraws_its_fields_and_says_why(self, admin):
        with self._ping(401):
            response = call(
                "admin_remote_add",
                admin,
                "post",
                {"name": "Peer", "base_url": "https://peer.example.com", "token": "bad"},
            )
        html = response.content.decode()

        assert response.status_code == 200
        assert 'hx-swap-oob="innerHTML:#add-remote-form"' in html
        assert response.messages == ["Authentication failed. Check your token."]
        assert not Remote.objects.filter(name="Peer").exists()


class TestEdit:
    def test_a_save_announces_the_change_and_keeps_a_blank_token(self, admin, registry):
        response = call(
            "admin_remote_edit",
            admin,
            "post",
            {"name": "Registry 2", "base_url": registry.base_url, "token": ""},
            remote_id=registry.pk,
        )

        registry.refresh_from_db()
        assert response.status_code == 204
        assert REMOTE_CHANGED in events(response)
        assert (registry.name, registry.token) == ("Registry 2", "secret-token-1234")

    def test_a_refused_save_redraws_its_fields(self, admin, registry):
        response = call(
            "admin_remote_edit",
            admin,
            "post",
            {"name": "", "base_url": registry.base_url},
            remote_id=registry.pk,
        )

        html = response.content.decode()
        assert 'hx-swap-oob="innerHTML:#edit-remote-form"' in html
        assert "This field is required." in html

    def test_the_drawer_is_titled_by_the_remote_and_offers_disconnect(self, admin, registry):
        html = call("admin_remote_edit_form", admin, remote_id=registry.pk).content.decode()

        assert '<h2 class="phoxtail-drawer__title">Registry</h2>' in html
        assert "Leave blank to keep secret…1234." in html
        assert "Disconnect remote" in html


class TestDisconnect:
    def test_a_disconnect_announces_the_change(self, admin, registry):
        response = call("admin_remote_delete", admin, "post", remote_id=registry.pk)

        assert response.status_code == 204
        assert REMOTE_CHANGED in events(response)
        assert not Remote.objects.exists()
