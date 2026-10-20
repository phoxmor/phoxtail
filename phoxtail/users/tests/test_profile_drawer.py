"""The Edit profile drawer: core's drawer, its fields in titled cards."""

from __future__ import annotations

import json

import pytest
from django.contrib.auth import get_user_model
from django.template.loader import render_to_string

from phoxtail.users.forms import UserProfileForm

User = get_user_model()

pytestmark = pytest.mark.urls("phoxtail.users.tests.urls")


@pytest.fixture
def member(db):
    return User.objects.create_user(username="member", email="member@example.com", first_name="Given")


@pytest.fixture
def html(member):
    context = {"form": UserProfileForm(instance=member), "user": member}
    return render_to_string("users/profile/partials/update_form.html", context)


def test_the_drawer_is_cores(html):
    assert '<h2 class="phoxtail-drawer__title">Edit profile</h2>' in html
    assert "phx-ground" in html
    assert html.count('onclick="closeModal(this)"') == 2  # close button, Close
    assert html.count('onclick="dismissModal(this)"') == 1  # click outside
    assert "closeModal()" not in html


def test_the_drawer_draws_only_cores_buttons(html):
    assert "phoxtail-btn" not in html
    assert html.index("Close</span>") < html.index('form="profile-update-form"')
    assert 'class="phx-button phx-button--primary" type="submit" form="profile-update-form"' in html


def test_the_fields_sit_in_titled_cards(html):
    assert html.count('class="phx-card"') == 2
    assert html.count('class="phx-card__title"') == 2
    assert 'name="first_name"' in html
    assert 'name="avatar"' in html


def test_a_save_disables_the_footer_while_it_runs(html):
    assert 'hx-disabled-elt="#base-modal .phoxtail-drawer__footer button"' in html


def _post(member, **data):
    from django.contrib.messages.storage.cookie import CookieStorage
    from django.test import RequestFactory

    from phoxtail.users.views import profile_update_view

    payload = {"first_name": "Given", "last_name": "Family", "phone_number_0": "", "phone_number_1": "", **data}
    request = RequestFactory().post("/profile/update/", payload)
    request.user = member
    request._messages = CookieStorage(request)
    return profile_update_view(request)


def test_a_save_closes_the_drawer_and_redraws_the_cards(member):
    response = _post(member, first_name="Renamed")
    assert json.loads(response.headers["HX-Trigger"]) == {"closeModal": {}}
    html = response.content.decode()
    assert 'hx-swap-oob="innerHTML:#profile-content"' in html
    assert "innerHTML:#core-modal-placeholder-wrapper" not in html
    member.refresh_from_db()
    assert member.first_name == "Renamed"


def test_a_refused_save_keeps_the_drawer_open_with_its_errors(member):
    response = _post(member, phone_number_0="GR", phone_number_1="123")
    assert "HX-Trigger" not in response.headers
    html = response.content.decode()
    assert 'hx-swap-oob="innerHTML:#profile-update-form-body"' in html
    assert "#profile-content" not in html


def test_the_page_is_four_tiles_each_with_its_buttons(member):
    """A save redraws the tiles whole: the member and Edit, their details,
    their contact, and their account with its username and buttons."""
    html = render_to_string("users/profile/partials/user_info.html", {"user": member})
    for tile in ("identity", "personal", "contact", "account"):
        assert f"usr-tile--{tile}" in html
    assert "usr-identity__edit" in html
    assert "Username" in html and member.username in html
    assert "Change password" in html and "Manage email" in html
