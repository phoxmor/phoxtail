"""Tests for ApiTrailingSlashMiddleware."""

from __future__ import annotations

import pytest
from django.http import HttpResponse
from django.test import RequestFactory

from phoxtail.api.middleware import ApiTrailingSlashMiddleware


def make_middleware(response: HttpResponse):
    """Return a middleware instance whose inner handler always returns *response*."""
    return ApiTrailingSlashMiddleware(get_response=lambda r: response)


@pytest.fixture()
def rf():
    return RequestFactory()


class TestSlashAppending:
    """Slash is appended to bare API paths; non-API and file-like paths are left alone."""

    def test_appends_slash_to_api_path_without_slash(self, rf):
        request = rf.get("/api/streams/v1/variants")
        make_middleware(HttpResponse())(request)
        assert request.path == "/api/streams/v1/variants/"
        assert request.path_info == "/api/streams/v1/variants/"

    def test_does_not_double_slash_api_path(self, rf):
        request = rf.get("/api/streams/v1/variants/")
        make_middleware(HttpResponse())(request)
        assert request.path == "/api/streams/v1/variants/"

    def test_does_not_touch_non_api_path(self, rf):
        request = rf.get("/admin/login")
        make_middleware(HttpResponse())(request)
        assert request.path == "/admin/login"

    def test_does_not_append_slash_to_file_like_path(self, rf):
        request = rf.get("/api/openapi.json")
        make_middleware(HttpResponse())(request)
        assert request.path == "/api/openapi.json"

    def test_does_not_append_slash_to_nested_file_like_path(self, rf):
        request = rf.get("/api/export.csv")
        make_middleware(HttpResponse())(request)
        assert request.path == "/api/export.csv"

    def test_does_not_touch_bare_api_prefix(self, rf):
        # "/api" doesn't start with "/api/" so it's outside the middleware's scope.
        request = rf.get("/api")
        make_middleware(HttpResponse())(request)
        assert request.path == "/api"


class TestI18nRedirectBlocking:
    """i18n redirects from LocaleMiddleware are replaced with JSON 404s."""

    def _redirect(self, location: str, status: int = 302) -> HttpResponse:
        r = HttpResponse(status=status)
        r["Location"] = location
        return r

    def test_blocks_english_i18n_redirect(self, rf):
        request = rf.get("/api/streams/v1/variants")
        response = make_middleware(self._redirect("/en/api/streams/v1/variants/"))(
            request
        )
        assert response.status_code == 404
        assert response["Content-Type"] == "application/json"

    def test_blocks_two_letter_language_redirect(self, rf):
        request = rf.get("/api/streams/v1/variants")
        response = make_middleware(self._redirect("/fr/api/streams/v1/variants/"))(
            request
        )
        assert response.status_code == 404

    def test_blocks_region_qualified_language_redirect(self, rf):
        request = rf.get("/api/streams/v1/variants")
        response = make_middleware(self._redirect("/zh-Hans/api/streams/v1/variants/"))(
            request
        )
        assert response.status_code == 404

    def test_passes_through_non_i18n_redirect(self, rf):
        request = rf.get("/api/oauth/callback")
        redirect = self._redirect("https://provider.example.com/auth")
        response = make_middleware(redirect)(request)
        assert response.status_code == 302

    def test_passes_through_redirect_without_location(self, rf):
        request = rf.get("/api/streams/v1/variants")
        redirect = HttpResponse(status=302)
        response = make_middleware(redirect)(request)
        assert response.status_code == 302

    def test_does_not_block_redirects_on_non_api_paths(self, rf):
        request = rf.get("/en/pages/")
        response = make_middleware(self._redirect("/en/pages/welcome/"))(request)
        assert response.status_code == 302
