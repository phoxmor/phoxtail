"""A search field shows a picked item only when it is one of its choices."""

import pytest
from django import forms
from django.contrib.auth import get_user_model

from phoxtail.core.fields import SingleSelectSearchField, render_field

pytestmark = pytest.mark.django_db


class PickForm(forms.Form):
    user = SingleSelectSearchField(queryset=get_user_model().objects.filter(is_active=True))


@pytest.fixture
def active():
    return get_user_model().objects.create_user(username="maria", email="maria@example.com")


@pytest.fixture
def inactive():
    return get_user_model().objects.create_user(username="nikos", email="nikos@example.com", is_active=False)


def test_a_picked_choice_is_shown_and_left_out_of_the_list(active):
    field = PickForm({"user": str(active.pk)})["user"]

    assert field.selected_item == active
    assert active not in field.available_items


def test_an_item_outside_the_choices_is_not_shown(active, inactive):
    field = PickForm({"user": str(inactive.pk)})["user"]

    assert field.selected_item is None
    assert list(field.available_items) == [active]


def test_a_value_that_is_not_a_key_picks_nothing(active):
    field = PickForm({"user": "abc"})["user"]

    assert field.selected_item is None
    assert list(field.available_items) == [active]


def test_django_draws_the_hidden_box_that_carries_the_pick(active):
    html = render_field("single_select_search", PickForm({"user": str(active.pk)})["user"])

    assert f'<input type="hidden" name="user" value="{active.pk}" id="id_user">' in html


def test_a_value_that_picks_nothing_sends_nothing(active):
    html = render_field("single_select_search", PickForm({"user": "abc"})["user"])

    assert 'name="user"' not in html


def test_the_trigger_is_named_by_the_label_and_the_pick(active):
    html = render_field("single_select_search", PickForm({"user": str(active.pk)})["user"])

    assert 'aria-labelledby="id_user_label id_user_pick"' in html
    assert 'id="id_user_label"' in html
    assert 'id="id_user_pick"' in html


def test_the_trigger_points_at_the_help_text_by_djangos_ids(active):
    class HelpForm(forms.Form):
        user = SingleSelectSearchField(queryset=get_user_model().objects.all(), help_text="Search for a user")

    html = render_field("single_select_search", HelpForm()["user"])

    assert 'aria-describedby="id_user_helptext"' in html
    assert 'id="id_user_helptext">Search for a user' in html


def test_errors_take_the_help_texts_place_under_the_field(active):
    html = render_field("single_select_search", PickForm({"user": ""})["user"])

    assert 'aria-describedby="id_user_error"' in html
    assert 'id="id_user_error"' in html


def test_the_search_field_carries_no_script_of_its_own(active):
    """Its panel and error line are handled once, in js/fields.js."""
    html = render_field("single_select_search", PickForm({"user": ""})["user"])

    assert "<script" not in html
    assert "data-single-select-search" in html
    assert "data-single-select-search-trigger" in html
