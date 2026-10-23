"""The profile URLConf with the code pages, which allauth mounts only when
code login or reset by code is on as its URLs are first imported."""

from allauth.account.views import ConfirmPasswordResetCodeView, RequestLoginCodeView
from django.urls import path

from phoxtail.users.tests.urls import urlpatterns as base

urlpatterns = [
    path("accounts/login/code/", RequestLoginCodeView.as_view(), name="account_request_login_code"),
    path(
        "accounts/password/reset/code/confirm/",
        ConfirmPasswordResetCodeView.as_view(),
        name="account_confirm_password_reset_code",
    ),
    *base,
]
