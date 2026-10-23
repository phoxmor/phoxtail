"""Login and signup are allauth's own pages, drawn with phoxtail's elements."""

import re
from pathlib import Path

import pytest
from allauth.account.forms import (
    ConfirmLoginCodeForm,
    RequestLoginCodeForm,
    ResetPasswordForm,
    ResetPasswordKeyForm,
)
from allauth.account.models import EmailAddress
from allauth.account.views import EmailView, LoginView, PasswordChangeView, SignupView
from allauth.core import context
from django import forms
from django.contrib.auth.models import AnonymousUser
from django.contrib.messages.storage.cookie import CookieStorage
from django.contrib.sessions.backends.signed_cookies import SessionStore
from django.template.loader import render_to_string
from django.test.signals import template_rendered
from django.utils import translation

import phoxtail.users

pytestmark = [pytest.mark.django_db, pytest.mark.urls("phoxtail.users.tests.urls")]

FORMS = {"login": "phoxtail.users.forms.LoginForm", "signup": "phoxtail.users.forms.SignupForm"}


@pytest.fixture(autouse=True)
def _allauth(settings):
    settings.ACCOUNT_FORMS = FORMS
    settings.LANGUAGES = [("en", "English")]


def _call(rf, view, method="get", path="/accounts/login/", data=None, user=None):
    request = getattr(rf, method)(path, data)
    request.user = user or AnonymousUser()
    request.session = SessionStore()
    request._messages = CookieStorage(request)
    with translation.override("en"), context.request_context(request):
        response = view.as_view()(request)
        if hasattr(response, "render"):
            response.render()
    return response


def _html(response):
    return response.content.decode()


class TestLogin:
    def test_a_wrong_password_is_said_above_the_form(self, rf):
        html = _html(
            _call(rf, LoginView, "post", data={"login": "nobody@example.com", "password": "wrong"}),
        )

        notice = re.search(r'<div class="phx-notice phx-notice--destructive" role="alert">(.*?)</div>', html, re.S)
        assert notice
        assert "not correct" in notice.group(1)

    def test_an_empty_submit_marks_each_field_not_the_form(self, rf):
        html = _html(_call(rf, LoginView, "post"))

        assert "phx-notice--destructive" not in html
        assert html.count("This field is required.") == 2

    def test_the_page_carries_next_through_the_form(self, rf):
        html = _html(_call(rf, LoginView, path="/accounts/login/?next=/x/"))

        assert '<input type="hidden" name="next" value="/x/">' in html

    def test_a_good_login_goes_to_next(self, rf, django_user_model):
        django_user_model.objects.create_user(email="reader@example.com", password="right-password")

        response = _call(
            rf,
            LoginView,
            "post",
            data={"login": "reader@example.com", "password": "right-password", "next": "/x/"},
        )

        assert response.status_code == 302
        assert response["Location"] == "/x/"

    def test_the_fields_are_drawn_in_core_frames(self, rf):
        html = _html(_call(rf, LoginView))

        assert 'name="login"' in html
        assert "autofocus" not in html
        assert 'type="password"' in html
        assert "phx-field" in html
        assert "Forgot your password?" in html

    @pytest.mark.urls("phoxtail.users.tests.code_urls")
    def test_a_sign_in_code_is_offered_under_or(self, rf, settings):
        settings.ACCOUNT_LOGIN_BY_CODE_ENABLED = True

        html = _html(_call(rf, LoginView))

        assert "auth-or" in html
        assert 'href="/accounts/login/code/"' in html

    def test_without_other_ways_in_there_is_no_or(self, rf):
        assert "auth-or" not in _html(_call(rf, LoginView))


class TestSignup:
    def test_the_fields_come_in_the_forms_order(self, rf, settings):
        settings.PHOXTAIL_ALLOW_SIGNUP = True

        html = _html(_call(rf, SignupView, path="/accounts/signup/"))

        assert "autofocus" not in html
        names = re.findall(r'<(?:input|select)[^>]*\bname="([a-z_0-9]+)"', html)
        drawn = [name for name in dict.fromkeys(names) if name not in ("csrfmiddlewaretoken", "language", "next")]
        assert drawn == [
            "first_name",
            "last_name",
            "email",
            "born_at",
            "gender",
            "country",
            "phone_number_0",
            "phone_number_1",
            "password1",
            "password2",
        ]

    def test_djangos_password_rules_are_shown(self, rf, settings):
        settings.PHOXTAIL_ALLOW_SIGNUP = True
        settings.AUTH_PASSWORD_VALIDATORS = [{"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"}]

        html = _html(_call(rf, SignupView, path="/accounts/signup/"))

        assert "Your password must contain at least 8 characters." in html

    def test_closed_signup_says_so_in_the_card(self, rf, settings):
        settings.PHOXTAIL_ALLOW_SIGNUP = False

        html = _html(_call(rf, SignupView, path="/accounts/signup/"))

        assert "Sign Up Closed" in html
        assert "phx-card" in html


@pytest.fixture
def reader(django_user_model):
    user = django_user_model.objects.create_user(email="reader@example.com", password="right-password")
    EmailAddress.objects.create(user=user, email=user.email, verified=True, primary=True)
    return user


class TestSignedIn:
    """Signed-in pages: allauth's "manage" layout, in the same frame."""

    def test_the_email_page_draws_each_address_as_a_choice_with_small_tags(self, rf, reader):
        html = _html(_call(rf, EmailView, path="/accounts/email/", user=reader))

        choice = re.search(r'<label for="[^"]*" class="phx-choice">(.*?)</label>', html, re.S)
        assert choice and "reader@example.com" in choice.group(1)
        assert 'class="phx-tag phx-tag--small phx-tag--success"' in choice.group(1)
        assert '<h2 class="phx-card__title auth-section">' in html

    def test_buttons_keep_their_normal_size(self, rf, reader):
        html = _html(_call(rf, EmailView, path="/accounts/email/", user=reader))

        assert "phx-button--danger" in html
        assert "phx-button--large" not in html

    def test_the_change_email_page_draws_its_fields_outlined(self, rf, reader):
        """Shown only where a project turns ACCOUNT_CHANGE_EMAIL on."""
        request = rf.get("/accounts/email/")
        request.user = reader
        with translation.override("en"):
            html = render_to_string(
                "account/email_change.html",
                {"form": EmailForm(), "current_emailaddress": EmailAddress.objects.get(user=reader)},
                request,
            )

        current = re.search(r'<input class="phx-field__control"[^>]*id="current_email"[^>]*>', html, re.S)
        assert current and "disabled" in current.group(0)
        assert 'value="reader@example.com"' in current.group(0)
        assert re.search(r'<input class="phx-field__control"[^>]*name="email"', html, re.S)

    def test_change_password_offers_the_reset_link_once(self, rf, reader):
        html = _html(_call(rf, PasswordChangeView, path="/accounts/password/change/", user=reader))

        assert html.count("Forgot your password?") == 1


class CodeForm(forms.Form):
    code = forms.CharField()


class EmailForm(forms.Form):
    email = forms.EmailField()


@pytest.mark.urls("phoxtail.users.tests.code_urls")
def test_a_page_phoxtail_never_copied_is_drawn_in_the_frame(rf):
    """Reset by code: allauth's own page, in phoxtail's frame and fields."""
    request = rf.get("/accounts/password/reset/code/confirm/")
    request.user = AnonymousUser()
    with translation.override("en"):
        html = render_to_string(
            "account/confirm_password_reset_code.html", {"verify_form": CodeForm(), "email": "x@example.com"}, request
        )

    assert "auth-card" in html
    assert 'name="code"' in html
    assert "phx-field" in html


@pytest.mark.urls("phoxtail.users.tests.code_urls")
@pytest.mark.parametrize(
    ("template", "context"),
    [
        ("account/password_reset.html", lambda: {"form": ResetPasswordForm()}),
        ("account/password_reset_from_key.html", lambda: {"form": ResetPasswordKeyForm(), "action_url": "/"}),
        ("account/request_login_code.html", lambda: {"form": RequestLoginCodeForm()}),
        (
            "account/confirm_login_code.html",
            lambda: {"verify_form": ConfirmLoginCodeForm(), "email": "x@example.com"},
        ),
        (
            "account/confirm_password_reset_code.html",
            lambda: {"verify_form": CodeForm(), "email": "x@example.com"},
        ),
    ],
)
def test_no_signed_out_form_moves_the_focus(rf, template, context):
    """allauth focuses no field, and a form drawn whole could start with one that takes no focus."""
    request = rf.get("/accounts/login/")
    request.user = AnonymousUser()
    with translation.override("en"):
        html = render_to_string(template, context(), request)

    assert "autofocus" not in html


@pytest.mark.parametrize(
    ("view", "path", "allow_signup", "signed_in"),
    [
        (LoginView, "/accounts/login/", False, False),
        (SignupView, "/accounts/signup/", True, False),
        (EmailView, "/accounts/email/", False, True),
    ],
)
def test_every_element_drawn_is_ours(rf, settings, request, view, path, allow_signup, signed_in):
    """An allauth element phoxtail does not override would draw in allauth's plain look."""
    settings.PHOXTAIL_ALLOW_SIGNUP = allow_signup
    user = request.getfixturevalue("reader") if signed_in else None
    ours = Path(phoxtail.users.__file__).parent / "templates"
    drawn = []

    def record(sender, template, **kwargs):
        if template.name and template.name.startswith("allauth/elements/"):
            drawn.append(Path(template.origin.name))

    template_rendered.connect(record)
    try:
        _call(rf, view, path=path, user=user)
    finally:
        template_rendered.disconnect(record)

    assert drawn
    assert [str(origin) for origin in drawn if ours not in origin.parents] == []
