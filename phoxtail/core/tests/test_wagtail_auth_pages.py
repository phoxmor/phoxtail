"""Wagtail's private-page login and page-password prompt sit on the auth card.

Both templates are named by the project settings (WAGTAIL_FRONTEND_LOGIN_TEMPLATE,
WAGTAIL_PASSWORD_REQUIRED_TEMPLATE) and render the forms Wagtail hands them, so
the fields they post must keep the names those views read.
"""

import pytest
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import AnonymousUser
from django.template.loader import render_to_string
from wagtail.forms import PasswordViewRestrictionForm
from wagtail.models import Page, PageViewRestriction

pytestmark = pytest.mark.django_db


def _render(rf, template, context, user=None):
    request = rf.get("/")
    request.user = user or AnonymousUser()
    return render_to_string(template, context, request=request)


def test_login_posts_the_fields_django_login_reads(rf):
    html = _render(rf, "wagtailadmin/pages/login.html", {"form": AuthenticationForm(), "next": "/private/"})

    assert 'name="username"' in html
    assert 'type="email"' in html
    assert 'name="password"' in html
    assert '<input type="hidden" name="next" value="/private/">' in html
    assert "auth-card" in html


def test_login_renders_without_allauth_urls(rf):
    """The reset link is offered where allauth is mounted, never required."""
    html = _render(rf, "wagtailadmin/pages/login.html", {"form": AuthenticationForm()})

    assert "Forgot your password?" not in html


def test_login_explains_itself_only_to_a_logged_in_visitor(rf, django_user_model):
    user = django_user_model.objects.create_user(email="reader@example.com", password="x")

    anonymous = _render(rf, "wagtailadmin/pages/login.html", {"form": AuthenticationForm()})
    logged_in = _render(rf, "wagtailadmin/pages/login.html", {"form": AuthenticationForm()}, user=user)

    assert "auth-note" not in anonymous
    assert "auth-note" in logged_in


def test_password_prompt_posts_to_wagtail_with_its_return_url(rf):
    restriction = PageViewRestriction(
        page=Page.get_first_root_node(), restriction_type=PageViewRestriction.PASSWORD, password="secret"
    )
    form = PasswordViewRestrictionForm(instance=restriction, initial={"return_url": "/private/"})

    html = _render(
        rf, "wagtailadmin/pages/password_required.html", {"form": form, "action_url": "/_util/authenticate/1/2/"}
    )

    assert 'action="/_util/authenticate/1/2/"' in html
    assert 'name="password"' in html
    assert 'name="return_url"' in html
    assert "auth-card" in html
