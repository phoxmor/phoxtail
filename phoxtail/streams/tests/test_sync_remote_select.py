"""The sync page's remote picker is the core search field's view."""

from __future__ import annotations

import pytest
from django.test import RequestFactory

from phoxtail.remotes.models import Remote
from phoxtail.streams.admin.sync.views import RemoteSelectView
from phoxtail.streams.tests.factories import UserFactory

# The view links to other admin views, so the tests mount the admin.
pytestmark = [pytest.mark.django_db, pytest.mark.urls("phoxtail.cms.tests.admin_urls")]


@pytest.fixture
def remotes():
    return [
        Remote.objects.create(name="Registry", base_url="https://registry.example.com", token="token"),
        Remote.objects.create(name="Staging", base_url="https://staging.example.com", token="token"),
    ]


def _get(user, **params):
    request = RequestFactory().get("/", params)
    request.user = user
    request.htmx = True
    return RemoteSelectView.as_view()(request)


def test_typing_lists_the_matching_remotes(remotes):
    html = _get(UserFactory(is_superuser=True, is_staff=True), remote_search="Registry").content.decode()

    assert "Registry" in html
    assert "Staging" not in html


def test_a_pick_loads_that_remotes_streams(remotes):
    registry = remotes[0]
    html = _get(UserFactory(is_superuser=True, is_staff=True), remote_select=str(registry.pk)).content.decode()

    assert f'<input type="hidden" name="remote" value="{registry.pk}" id="id_remote">' in html
    assert f"?remote={registry.pk}" in html


def test_a_clear_goes_back_to_local(remotes):
    html = _get(
        UserFactory(is_superuser=True, is_staff=True), remote=str(remotes[0].pk), remote_clear="1"
    ).content.decode()

    assert 'name="remote"' not in html.split('id="remote-selected-value"')[1].split("</div>")[0]
    assert "?mode=local" in html


def test_a_user_who_cannot_manage_remotes_is_refused(remotes):
    response = _get(UserFactory(), remote_search="Registry")

    assert response.status_code == 204
