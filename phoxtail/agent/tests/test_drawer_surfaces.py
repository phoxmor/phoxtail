"""The bar's drawers rise from the page; what floats above them is a popover.

The page is the ground, so a drawer painted the ground's gray would melt
into it. Each drawer carries core's ``phx-raised`` instead: the risen color,
and the cut-in values for the controls inside it. Without the class the
drawer has no background of its own at all, since the glass it used to paint
is gone.

The dock floats above the page, and its Actions, Blocks and Inference menus
above it; the collection menu floats above a drawer. Each carries
``phx-popover``.
"""

from __future__ import annotations

import re

import pytest
from django.contrib.auth.context_processors import PermWrapper
from django.template.loader import render_to_string
from django.test import RequestFactory

pytestmark = [
    pytest.mark.django_db,
    pytest.mark.urls("phoxtail.cms.tests.bar_urls"),
]


@pytest.fixture
def operator(django_user_model):
    return django_user_model.objects.create_superuser(username="boss", email="boss@example.invalid", password="x")


def _view(view_name, user):
    from phoxtail.agent import views

    request = RequestFactory().get("/")
    request.user = user
    request.htmx = False
    return getattr(views, view_name)(request).content.decode()


def _bar(user, page=None):
    request = RequestFactory().get("/")
    request.user = user
    return render_to_string(
        "phoxtail_cms/phoxtail_bar.html",
        {"user": user, "perms": PermWrapper(user), "page": page},
        request=request,
    )


@pytest.fixture
def page():
    from wagtail.models import Site

    return Site.objects.get(is_default_site=True).root_page.specific


def _classes(html, marker):
    """The class list of the element whose opening tag holds ``marker``."""
    tag = re.search(r"<[^>]*" + re.escape(marker) + r"[^>]*>", html).group(0)
    return re.search(r'class="([^"]*)"', tag).group(1).split()


def test_the_chatbot_drawer_rises(operator):
    assert "phx-raised" in _classes(_bar(operator), 'id="phoxtail-chatbot-drawer"')


def test_the_inference_panel_is_a_popover(operator):
    html = _bar(operator)
    assert "phx-popover" in _classes(html, 'id="phoxtail-model-picker-panel"')


def test_the_media_picker_rises(operator):
    html = _view("media_picker", operator)
    assert "phx-raised" in _classes(html, "phoxtail-media-picker-drawer")


def test_the_collection_menu_is_a_popover(operator):
    html = _view("media_picker", operator)
    assert "phx-popover" in _classes(html, 'id="phoxtail-media-picker-collection-panel"')


def test_the_chat_history_rises(operator):
    html = _view("chat_history", operator)
    assert "phx-raised" in _classes(html, "phoxtail-chat-history-drawer")


def test_the_dock_is_a_popover(operator):
    assert "phx-popover" in _classes(_bar(operator), 'class="phoxtail-bar-dock')


def test_the_actions_menu_is_a_popover(operator):
    assert "phx-popover" in _classes(_bar(operator), 'id="phoxtail-bar-actions-panel"')


def test_the_blocks_menu_is_a_popover(operator, page):
    html = _bar(operator, page)
    assert "phx-popover" in _classes(html, 'id="phoxtail-bar-blocks-panel"')
