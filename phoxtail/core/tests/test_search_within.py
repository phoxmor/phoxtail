"""A search field searches only its allowed choices, however the form narrowed them."""

import pytest
from django.contrib.auth import get_user_model

from phoxtail.core.views import _search_within

pytestmark = pytest.mark.django_db


@pytest.fixture
def users():
    User = get_user_model()
    return [
        User.objects.create_user(username=name, email=f"{name}@example.com", first_name=first)
        for name, first in [("maria", "Maria"), ("marina", "Marina"), ("mario", "Mario"), ("nikos", "Nikos")]
    ]


def test_a_list_narrowed_on_an_unindexed_column_can_be_searched(users):
    maria, marina, mario, _ = users
    allowed = get_user_model().objects.filter(date_joined__isnull=False).exclude(pk=maria.pk)

    found = _search_within(allowed, "mar", limit=20)

    assert maria not in found
    assert {marina, mario} <= set(found)


def test_only_the_allowed_rows_are_found(users):
    maria, *_ = users
    allowed = get_user_model().objects.filter(pk=maria.pk)

    assert _search_within(allowed, "mar", limit=20) == [maria]


def test_the_matches_are_cut_at_the_limit(users):
    found = _search_within(get_user_model().objects.all(), "mar", limit=2)

    assert len(found) == 2


def test_the_matches_keep_the_lists_related_loading(users, django_assert_num_queries):
    allowed = get_user_model().objects.prefetch_related("groups")
    found = _search_within(allowed, "mar", limit=20)

    assert found
    with django_assert_num_queries(0):
        [list(user.groups.all()) for user in found]
