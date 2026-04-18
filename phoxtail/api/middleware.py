"""Middleware for the Phoxtail API.

``ApiTrailingSlashMiddleware`` normalizes requests under ``/api/`` so that
both ``/api/foo`` and ``/api/foo/`` resolve to the same django-ninja route
*without* issuing a redirect. This avoids two problems:

1. Django's built-in ``APPEND_SLASH`` answers the non-slash form with a
   301/302 redirect. Most API clients (httpx, requests, fetch) don't
   follow redirects by default, and for POST/PUT/PATCH the body is
   silently dropped when the method is rewritten to GET.
2. In a hatched Phoxtail project the wagtail ``i18n_patterns`` catch-all
   sits at the bottom of ``urls.py``. If a rewritten URL fails to match
   a ninja pattern it falls through and gets swallowed by wagtail's
   ``/en/...`` redirect, producing a confusing HTML 404 for what should
   have been a clean JSON response.

The middleware is scoped to paths starting with ``/api/`` so non-API
routes (wagtail pages, admin, i18n) keep Django's default slash
semantics.

File-like paths (last segment contains a dot, e.g. ``/api/openapi.json``)
are intentionally excluded from slash-appending — a trailing slash on a
file extension URL is invalid.

See vitalik/django-ninja#1058 for the upstream discussion.
"""

from __future__ import annotations

import re
from collections.abc import Callable

from django.http import HttpRequest, HttpResponse, JsonResponse

API_PREFIX = "/api/"

# Matches a path whose first segment is a BCP-47 language tag, which is
# the shape of URLs that Django's LocaleMiddleware produces when it hijacks
# an API 404 (e.g. "/en/api/...", "/fr/api/...").
_LANG_PREFIX_RE = re.compile(r"^/[a-z]{2,3}(-[a-zA-Z]{2,4})?/")


class ApiTrailingSlashMiddleware:
    """Normalize trailing slashes for API requests and guard against i18n hijacking.

    In addition to the slash rewriting described in the module docstring,
    this middleware prevents ``LocaleMiddleware`` from intercepting API
    404 responses.  When django-ninja returns a 404 (e.g. "variant not
    found"), ``LocaleMiddleware.process_response`` sees the 404 and
    checks whether prepending a language prefix (``/en/api/...``) would
    resolve.  It does — via wagtail's i18n catch-all — so it issues a
    302 redirect, and the client ends up with an HTML error page instead
    of the JSON 404 it should have received.

    To prevent this, any 3xx redirect whose ``Location`` header matches a
    language prefix is replaced with a JSON 404.  Legitimate redirects
    originating from ``/api/`` paths (e.g. OAuth callbacks) are left
    untouched.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        path = request.path
        is_api = path.startswith(API_PREFIX)
        last_segment = path.rsplit("/", 1)[-1]
        if is_api and not path.endswith("/") and "." not in last_segment:
            new_path = f"{path}/"
            request.path = new_path
            request.path_info = new_path
        response = self.get_response(request)
        # Block LocaleMiddleware's i18n redirects for API paths only.
        if is_api and 300 <= response.status_code < 400:
            location = response.get("Location", "")
            if _LANG_PREFIX_RE.match(location):
                return JsonResponse({"detail": "Not found."}, status=404)
        return response
