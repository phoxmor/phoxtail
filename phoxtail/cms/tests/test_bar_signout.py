"""The Actions menu ends with a way out.

Signing out changes state, so allauth takes it only as a POST carrying the
CSRF token: the item is a submit button inside a form, not a link.
"""

from __future__ import annotations

import re

import pytest
from django.contrib.auth.context_processors import PermWrapper
from django.template.loader import render_to_string
from django.test import RequestFactory
from django.urls import reverse

pytestmark = [
    pytest.mark.django_db,
    pytest.mark.urls("phoxtail.cms.tests.bar_urls"),
]


@pytest.fixture
def operator(django_user_model):
    return django_user_model.objects.create_superuser(username="boss", email="boss@example.invalid", password="x")


def _actions_menu(user):
    request = RequestFactory().get("/")
    request.user = user
    html = render_to_string(
        "phoxtail_cms/phoxtail_bar.html",
        {"user": user, "perms": PermWrapper(user), "page": None},
        request=request,
    )
    start = html.index('id="phoxtail-bar-actions-panel"')
    return html[start : html.index('id="phoxtail-chatbot-drawer"', start)]


def test_sign_out_posts_to_the_logout_view(operator):
    menu = _actions_menu(operator)
    form = re.search(r"<form[^>]*>.*?</form>", menu, re.S).group(0)
    assert 'method="post"' in form
    assert f'action="{reverse("account_logout")}"' in form
    assert "csrfmiddlewaretoken" in form
    assert 'id="phoxtail-bar-signout-btn"' in form
    assert 'type="submit"' in form


def test_sign_out_is_the_last_item(operator):
    items = re.findall(r"<(?:a|button)\b[^>]*phoxtail-bar-actions-item[^>]*>", _actions_menu(operator), re.S)
    assert 'id="phoxtail-bar-signout-btn"' in items[-1]
