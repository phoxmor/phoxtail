"""Who sees the phoxtail bar, and which of its buttons.

The bar used to be wrapped in a single ``user.is_superuser`` check, which
answered for every item inside it — so the per-item permission checks it
already contained could only ever be read by someone who passed them
anyway. Granting ``access_chatbot`` did nothing: the person had the
permission and no way to reach what it opened.

The items ask different questions, and that is the whole of the fix. The
chat and media buttons open agent views gated on ``access_chatbot``; the
page controls and admin links lead where only an operator can go. So the
wrapper asks whether a person can use *anything* here, and each item asks
its own question.

This is asserted by rendering, because a template's conditions cannot be
checked any other way — nothing imports them and no type sees them.
"""

from __future__ import annotations

import pytest
from django.contrib.auth.context_processors import PermWrapper
from django.contrib.auth.models import Group, Permission
from django.template.loader import render_to_string
from django.test import RequestFactory

# The bar reaches the agent views and the dashboard by name, and a missing
# route renders as an empty string rather than an error — so without these
# mounted the media button is absent for everyone and its test proves
# nothing. See ``bar_urls``.
pytestmark = [pytest.mark.django_db, pytest.mark.urls("phoxtail.cms.tests.bar_urls")]

BAR = 'id="phoxtail-bar"'
CHAT = "phoxtail-bar-chatbot-btn"
MEDIA = "phoxtail-bar-media-btn"
ACTIONS = "phoxtail-bar-actions-btn"
ADMIN = "phoxtail-bar-admin-btn"
CHAT_MEDIA = "phoxtail-chatbot-media-btn"


def _render(user, page=None):
    request = RequestFactory().get("/")
    request.user = user
    return render_to_string(
        "phoxtail_cms/phoxtail_bar.html",
        {"user": user, "perms": PermWrapper(user), "page": page},
        request=request,
    )


@pytest.fixture
def chat_only(django_user_model):
    user = django_user_model.objects.create_user(username="chatter", email="chatter@example.invalid", password="x")
    group = Group.objects.create(name="chatters")
    group.permissions.add(Permission.objects.get(content_type__app_label="phoxtail_agent", codename="access_chatbot"))
    user.groups.add(group)
    return django_user_model.objects.get(pk=user.pk)


@pytest.fixture
def nobody(django_user_model):
    return django_user_model.objects.create_user(username="nobody", email="nobody@example.invalid", password="x")


@pytest.fixture
def operator(django_user_model):
    return django_user_model.objects.create_superuser(username="boss", email="boss@example.invalid", password="x")


class TestWhoSeesTheBar:
    def test_someone_who_can_use_nothing_sees_nothing(self, nobody):
        assert BAR not in _render(nobody)

    def test_granting_chatbot_access_reaches_the_chat_button(self, chat_only):
        """The regression this file exists for.

        The permission was grantable from the Wagtail admin and opened
        nothing, because the outer check answered first.
        """
        html = _render(chat_only)
        assert BAR in html
        assert CHAT in html

    def test_an_operator_still_sees_everything(self, operator):
        html = _render(operator)
        assert all(item in html for item in (BAR, CHAT, MEDIA, CHAT_MEDIA, ACTIONS, ADMIN))


class TestWhatEachPersonSees:
    def test_chat_access_does_not_carry_the_page_and_admin_controls(self, chat_only):
        """Opening the bar is not opening what is on it.

        Publishing, editing and the admin links are a different authority
        from talking to the chatbot, and the bar appearing must not be
        read as a grant of them.
        """
        html = _render(chat_only)
        assert ACTIONS not in html
        assert ADMIN not in html

    def test_the_media_picker_is_withheld_from_chat_access(self, chat_only, operator):
        """Chat access is not access to the library.

        The picker returns every image, document and collection in the
        project, unnarrowed — so it asks the same question the page
        controls do, not the one the chat button asks. Both buttons that
        open it are checked, because there are two: one on the bar and one
        inside the chat composer, and the second had no check at all.
        """
        chatter = _render(chat_only)
        assert MEDIA not in chatter
        assert CHAT_MEDIA not in chatter

        boss = _render(operator)
        assert MEDIA in boss
        assert CHAT_MEDIA in boss

    def test_the_page_controls_need_more_than_chat_access(self, chat_only, operator, page_stub):
        """Asserted with a page present, because without one they are
        absent for everyone and the check would prove nothing."""
        assert "phoxtail-bar-page-info" not in _render(chat_only, page=page_stub)
        assert "phoxtail-bar-page-info" in _render(operator, page=page_stub)


@pytest.fixture
def page_stub():
    """The little a page needs to render the bar's page block."""
    from types import SimpleNamespace

    return SimpleNamespace(
        id=1,
        title="A page",
        slug="a-page",
        live=True,
        content_type=SimpleNamespace(app_label="phoxtail_cms", model="contentpage"),
        locale=SimpleNamespace(language_code="en"),
    )
