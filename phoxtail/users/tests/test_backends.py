"""Every project gets allauth's authentication backend beside Django's."""

import pytest
from allauth.account.views import LoginView, ReauthenticateView
from allauth.core import context
from django.contrib.auth import authenticate
from django.contrib.messages.storage.cookie import CookieStorage
from django.contrib.sessions.backends.signed_cookies import SessionStore
from django.utils import translation

pytestmark = [pytest.mark.django_db, pytest.mark.urls("phoxtail.users.tests.urls")]


def _request(rf, path, data, user=None):
    from django.contrib.auth.models import AnonymousUser

    request = rf.post(path, data)
    request.user = user or AnonymousUser()
    request.session = SessionStore()
    request._messages = CookieStorage(request)
    return request


def test_both_backends_are_set(settings):
    assert settings.AUTHENTICATION_BACKENDS == [
        "django.contrib.auth.backends.ModelBackend",
        "allauth.account.auth_backends.AuthenticationBackend",
    ]


def test_a_user_with_a_username_can_confirm_their_password(rf, django_user_model):
    user = django_user_model.objects.create_user(email="reader@example.com", password="right-password")
    user.username = "reader"
    user.save()
    request = _request(rf, "/accounts/reauthenticate/", {"password": "right-password"}, user)

    with translation.override("en"), context.request_context(request):
        response = ReauthenticateView.as_view()(request)

    assert response.status_code == 302


def test_an_inactive_user_is_shown_the_inactive_page(rf, django_user_model):
    django_user_model.objects.create_user(email="gone@example.com", password="right-password", is_active=False)
    request = _request(rf, "/accounts/login/", {"login": "gone@example.com", "password": "right-password"})

    with translation.override("en"), context.request_context(request):
        response = LoginView.as_view()(request)

    assert response.status_code == 302
    assert response["Location"] == "/accounts/inactive/"


def test_an_inactive_user_is_still_not_authenticated(django_user_model):
    """allauth's backend lets one through only to its own inactive page; Django's
    authenticate() (the Wagtail login, a token's password grant) still refuses."""
    django_user_model.objects.create_user(email="gone@example.com", password="right-password", is_active=False)

    assert authenticate(None, email="gone@example.com", password="right-password") is None
    assert authenticate(None, username="gone@example.com", password="right-password") is None


def test_a_username_does_not_log_in(django_user_model):
    """Login is by email only (ACCOUNT_LOGIN_METHODS), so allauth's backend
    does not match a username either; confirming a password works because
    allauth passes the email beside it."""
    user = django_user_model.objects.create_user(email="reader@example.com", password="right-password")
    user.username = "reader"
    user.save()

    assert authenticate(None, username="reader", password="right-password") is None
