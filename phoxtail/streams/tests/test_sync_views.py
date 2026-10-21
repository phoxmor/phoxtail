"""The sync page on core: its list, a variant's drawer and the Pull/Push cycle."""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest import mock

import pytest
from django.contrib.messages.storage.cookie import CookieStorage
from django.core.exceptions import ValidationError
from django.test import RequestFactory
from django_htmx.middleware import HtmxDetails

from phoxtail.remotes.models import Remote
from phoxtail.streams.admin.sync import views
from phoxtail.streams.tests.factories import BlockVariantFactory, UserFactory

# The name a change to a variant goes out under (core's change_event): pinned,
# so a rename fails here.
VARIANT_CHANGED = "phoxtail_streams.blockvariant:changed"

# The page, the list and the drawer link to admin views and core's modal.
pytestmark = [pytest.mark.django_db, pytest.mark.urls("phoxtail.streams.tests.sync_admin_urls")]


@pytest.fixture
def admin():
    return UserFactory(is_superuser=True, is_staff=True)


def call(view, person, method="get", data=None, htmx=True):
    headers = {"HTTP_HX_REQUEST": "true"} if htmx else {}
    request = getattr(RequestFactory(), method)("/", data or {}, **headers)
    request.user = person
    request.htmx = HtmxDetails(request)
    request._messages = CookieStorage(request)
    response = getattr(views, view)(request)
    response.messages = [str(m) for m in request._messages._queued_messages]
    return response


class TestPage:
    def test_the_page_stands_on_the_ground_and_redraws_on_a_change(self, admin):
        html = call("admin_sync_index", admin, htmx=False).content.decode()

        assert "phx-ground" in html
        assert f"load, {VARIANT_CHANGED} from:body" in html
        assert "ss-" not in html

    def test_the_list_answers_out_of_band_with_its_count(self, admin):
        BlockVariantFactory.create_batch(views._DEFAULT_LIMIT + 1)
        html = call("admin_sync_streams", admin, data={"mode": "local", "filter-page": "2"}).content.decode()

        assert 'hx-swap-oob="innerHTML:#streams-results"' in html
        assert 'hx-swap-oob="innerHTML:#sync-search-form"' in html
        assert f"{views._DEFAULT_LIMIT + 1} results" in html
        assert html.count("phx-card__button") == 1


class TestDrawer:
    def test_a_local_variant_shows_its_fields_line_by_line_and_is_titled_by_its_name(self, admin):
        variant = BlockVariantFactory(name="Stacked Panels", identifier="stacked-panels")
        html = call(
            "admin_sync_variant_detail", admin, data={"variant_id": variant.pk, "mode": "local"}
        ).content.decode()

        assert '<h2 class="phoxtail-drawer__title">' in html and "Stacked Panels" in html
        assert '<div class="sync-details__value sync-details__value--code">stacked-panels</div>' in html
        # Not the {% block %} tag's own name ("body"), which shadows a context "block".
        assert f'<div class="sync-details__value">{variant.block.name}</div>' in html
        assert "phx-tag" not in html and "phx-field__control" not in html
        # No remote: nothing to stand against, so no Sync section.
        assert ">Status<" not in html

    def test_previews_offer_only_the_devices_with_a_picture(self):
        images, form = views._previews({"preview_desktop_light_url": "/d.png", "preview_mobile_dark_url": "/m.png"})

        assert [i["device"] for i in images] == ["desktop", "mobile"]
        assert [value for value, _ in form.fields["device"].choices] == ["desktop", "mobile"]

    def test_no_pictures_no_previews(self):
        assert views._previews({}) == ([], None)


class TestPull:
    @pytest.fixture
    def remote(self):
        return Remote.objects.create(name="Registry", base_url="https://registry.example.com", token="t")

    def test_a_pull_announces_the_change_and_closes(self, admin, remote):
        result = SimpleNamespace(variant=SimpleNamespace(name="Stacked Panels"))
        with mock.patch.object(views.StreamsSyncService, "pull", return_value=result):
            response = call("admin_sync_pull", admin, "post", {"remote_id": remote.pk, "variant_id": "7"})

        assert response.status_code == 204
        assert {VARIANT_CHANGED, "closeModal", "showToast"} <= json.loads(response["HX-Trigger"]).keys()

    def test_a_refused_push_keeps_the_drawer_and_says_why(self, admin, remote):
        with mock.patch.object(views.StreamsSyncService, "push", side_effect=ValidationError("Schema differs.")):
            response = call("admin_sync_push", admin, "post", {"remote_id": remote.pk, "variant_id": "7"})

        assert response.status_code == 200
        assert "HX-Trigger" not in response
        assert response.messages == ["Schema differs."]
