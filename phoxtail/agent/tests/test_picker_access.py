"""The pickers are reachable by whoever may see everything they show.

Hiding a button is not closing a door. The media, menu and collection
pickers used to ask for ``access_chatbot``, the same permission as the
chat button beside them — and they return every image, document and
collection in the project, unnarrowed. So anyone granted chat access
could read the whole library by requesting the URL, whether or not a
button was rendered for them.

Pages are the exception and were already right: ``_explorable_pages``
narrows them to what the Wagtail explorer would show. It is the rest of
the picker that could not honestly ask a narrower question than "may you
see all of it".

These drive the views, because the template tests next door assert only
what is offered — and the gap between what is offered and what answers is
exactly the failure being fixed.
"""

from __future__ import annotations

import pytest
from django.contrib.auth.models import Group, Permission

# The urlconf is for the templates these views render, not for routing to
# them — the pickers reverse agent routes in their own markup, and a
# missing one raises where the permission check is what is under test.
pytestmark = [
    pytest.mark.django_db,
    pytest.mark.urls("phoxtail.cms.tests.bar_urls"),
]

# Called directly rather than over the test client: the shared test
# settings install no session app, so there is nobody to log in as, and
# these are about each view's own decision rather than its routing.
PICKERS = ["media_picker", "collection_picker", "menu_picker_children"]


def _call(rf, view_name, user):
    from phoxtail.agent import views

    request = rf.get("/")
    request.user = user
    request.htmx = False
    return getattr(views, view_name)(request)


@pytest.fixture
def chat_only(django_user_model):
    user = django_user_model.objects.create_user(username="chatter", email="chatter@example.invalid", password="x")
    group = Group.objects.create(name="chatters")
    group.permissions.add(Permission.objects.get(content_type__app_label="phoxtail_agent", codename="access_chatbot"))
    user.groups.add(group)
    return django_user_model.objects.get(pk=user.pk)


@pytest.mark.parametrize("view_name", PICKERS)
def test_chat_access_does_not_open_the_library(rf, chat_only, view_name):
    from django.core.exceptions import PermissionDenied

    with pytest.raises(PermissionDenied):
        _call(rf, view_name, chat_only)


@pytest.mark.parametrize("view_name", PICKERS)
def test_an_anonymous_caller_is_refused(rf, view_name):
    """The shape most likely to arrive at one of these URLs uninvited."""
    from django.contrib.auth.models import AnonymousUser
    from django.core.exceptions import PermissionDenied

    with pytest.raises(PermissionDenied):
        _call(rf, view_name, AnonymousUser())


def test_the_model_picker_keeps_chat_access_on_purpose(rf, chat_only):
    """The one picker that is not an operator surface, and why.

    It already asks the per-user question the others could not: each
    model artifact may name a permission, and the view keeps only the
    ones this person holds. So it shows what *they* may use rather than
    everything there is, which is exactly the property the media picker
    lacked. Asserted rather than left to omission — it is the only picker
    still on the old gate, and silence there reads as an oversight.
    """
    assert _call(rf, "model_picker_panel", chat_only).status_code == 200


def test_an_operator_reaches_them(rf, django_user_model):
    """The other half: a gate that refuses everyone is not a gate.

    Only the media picker is driven, because the other two want
    parameters and what is asserted here is reachability.
    """
    boss = django_user_model.objects.create_superuser(username="boss", email="boss@example.invalid", password="x")
    assert _call(rf, "media_picker", boss).status_code == 200


def test_a_deactivated_operator_is_not_one(rf, django_user_model):
    """``is_superuser`` alone admits someone who has been turned off.

    Shipped in the decorator rather than left to each view, because a
    view writing the check by hand reaches for ``user.is_superuser`` and
    forgets the other half.
    """
    from django.core.exceptions import PermissionDenied

    gone = django_user_model.objects.create_superuser(username="gone", email="gone@example.invalid", password="x")
    gone.is_active = False
    with pytest.raises(PermissionDenied):
        _call(rf, "media_picker", gone)


def test_the_chat_history_still_asks_only_for_chat_access(rf, chat_only):
    """The gate moved for the pickers and must not have moved for chat.

    Widening the check to the whole app would have quietly withdrawn the
    chatbot from everyone it was just opened to.
    """
    assert _call(rf, "chat_history", chat_only).status_code == 200
