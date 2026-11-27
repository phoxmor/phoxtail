"""The admin login URL hands over to allauth's login page, carrying ``next`` for a
logged-out visitor."""

from urllib.parse import parse_qs, urlparse

import pytest
from django.contrib.auth.models import AnonymousUser
from django.urls import reverse

from phoxtail.users.views import redirect_to_allauth_login

pytestmark = [pytest.mark.django_db, pytest.mark.urls("phoxtail.users.tests.urls")]


def _get(rf, data=None, user=None):
    request = rf.get("/admin/login/", data)
    request.user = user or AnonymousUser()
    return redirect_to_allauth_login(request)


class TestRedirect:
    def test_next_travels_to_the_login_page(self, rf):
        next_url = "/admin/pages/?q=a%20b&p=2"

        response = _get(rf, {"next": next_url})

        location = urlparse(response["Location"])
        assert response.status_code == 302
        assert location.path == reverse("account_login")
        assert parse_qs(location.query) == {"next": [next_url]}

    @pytest.mark.parametrize("data", [None, {"next": ""}])
    def test_without_next_the_login_page_has_no_query(self, rf, data):
        response = _get(rf, data)

        assert response["Location"] == reverse("account_login")

    def test_a_logged_in_user_loses_next_so_the_admin_cannot_loop(self, rf, django_user_model):
        user = django_user_model.objects.create_user(email="reader@example.com", password="right-password")

        response = _get(rf, {"next": "/admin/"}, user=user)

        assert response["Location"] == reverse("account_login")
