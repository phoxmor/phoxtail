"""The system check names a searched model the search engine cannot narrow."""

from types import ModuleType

import pytest
from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import override_settings
from django.urls import include, path

from phoxtail.core.checks import searched_models
from phoxtail.core.fields import SingleSelectSearchField
from phoxtail.core.views import SingleSelectSearchView


class TeamForm(forms.Form):
    team = SingleSelectSearchField(queryset=Group.objects.none())


class MemberForm(forms.Form):
    member = SingleSelectSearchField(queryset=get_user_model().objects.none())


class TeamSearch(SingleSelectSearchView):
    form_class = TeamForm
    field_name = "team"
    search_url_name = "team-search"


class MemberSearch(SingleSelectSearchView):
    form_class = MemberForm
    field_name = "member"
    search_url_name = "member-search"


nested = [path("teams/", TeamSearch.as_view(), name="team-search")]
urlpatterns = [path("admin/", include(nested)), path("members/", MemberSearch.as_view(), name="member-search")]


@pytest.mark.urls(__name__)
def test_a_model_without_its_key_as_filter_field_is_named():
    [error] = searched_models(None)

    assert error.id == "phoxtail_core.E003"
    assert error.obj is Group
    assert "Group is searched by TeamSearch" in error.msg
    assert error.hint == 'Make Group an index.Indexed model. Add index.FilterField("id") to Group.search_fields.'


def test_a_view_routed_twice_is_named_once():
    routes = ModuleType("routes")
    routes.urlpatterns = [path("a/", TeamSearch.as_view()), path("b/", TeamSearch.as_view())]

    with override_settings(ROOT_URLCONF=routes):
        [error] = searched_models(None)

    assert error.msg.count("TeamSearch") == 1
