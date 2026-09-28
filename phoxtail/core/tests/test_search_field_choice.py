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
