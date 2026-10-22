"""A program reads English unless it asks for another language.

By the time a door is checked, the middleware has already picked a language
from the cookie a browser set or from the site's default. Neither was asked
for by a program holding a token, so the door sets the language from
``Accept-Language`` alone. A browser session keeps its person's choice.
``translation.override`` stands in for the middleware's pick, since these
settings run without it.
"""

from __future__ import annotations

import pytest
from django.db.models import Field
from django.test import RequestFactory
from django.utils import translation
from ninja.errors import HttpError
from ninja.testing import TestClient

from phoxtail.api import api
from phoxtail.api.auth import Authorize, PhoxtailSessionAuth, authenticated
from phoxtail.core.authorization import AuthorizationContext
from phoxtail.tokens.ninja import PhoxtailTokenAuth
from phoxtail.tokens.tests.factories import AccessTokenFactory, UserFactory

pytestmark = pytest.mark.django_db

# A language both Django and phoxtail ship a catalogue for, so that every
# message under test really changes when the language does.
OTHER = "el"
BLANK_LAZY = Field.default_error_messages["blank"]
BLANK = "This field cannot be blank."


@pytest.fixture(autouse=True)
def _restore_language():
    # A door activates a language for the rest of the request; in tests
    # there is no middleware to reset it for the next one.
    with translation.override(translation.get_language()):
        yield


def _token_request(token, **headers):
    return RequestFactory().get("/api/", HTTP_AUTHORIZATION=f"Bearer {token._raw_token}", **headers)


class TestTheDoor:
    def test_a_token_reads_english_whatever_was_picked_before(self):
        request = _token_request(AccessTokenFactory())
        request.COOKIES["django_language"] = OTHER
        translation.activate(OTHER)

        authenticated()[0](request)

        assert translation.get_language() == "en"
        assert request.LANGUAGE_CODE == "en"

    def test_a_token_gets_the_language_it_asks_for(self):
        request = _token_request(AccessTokenFactory(), HTTP_ACCEPT_LANGUAGE=f"{OTHER},en;q=0.5")

        authenticated()[0](request)

        assert translation.get_language() == OTHER

    def test_an_unsupported_language_falls_back_to_english(self):
        request = _token_request(AccessTokenFactory(), HTTP_ACCEPT_LANGUAGE="xx")
        translation.activate(OTHER)

        authenticated()[0](request)

        assert translation.get_language() == "en"

    def test_any_kind_of_token_counts(self):
        # Not only phoxtail's own keys: a credential the authorization
        # server issued reaches the door the same way.
        def issued_backend(request):
            return AuthorizationContext(user=UserFactory(), token=object())

        translation.activate(OTHER)
        Authorize(issued_backend, lambda context: True)(RequestFactory().get("/api/"))

        assert translation.get_language() == "en"

    def test_a_refused_token_leaves_the_language_alone(self):
        request = RequestFactory().get("/api/", HTTP_AUTHORIZATION="Bearer phxt_nope")
        translation.activate(OTHER)

        authenticated()[0](request)

        assert translation.get_language() == OTHER

    def test_a_browser_session_keeps_its_language(self):
        request = RequestFactory().get("/api/")
        request.user = UserFactory()
        translation.activate(OTHER)

        Authorize(PhoxtailSessionAuth(), lambda context: True)(request)

        assert translation.get_language() == OTHER


class TestWhatTheCallerReads:
    """Through the real API: the words that come back, not just the switch."""

    def test_a_refusal_is_written_in_english(self):
        # The language is set before the predicate runs, so whatever it
        # says when it refuses is already in the caller's language.
        seen = []

        def refuse(context):
            seen.append(translation.get_language())
            return False

        translation.activate(OTHER)
        with pytest.raises(HttpError):
            Authorize(PhoxtailTokenAuth(), refuse)(_token_request(AccessTokenFactory()))

        assert seen == ["en"]

    @staticmethod
    def _blank_gender(start, **headers):
        token = AccessTokenFactory(user=UserFactory(is_superuser=True))
        translation.activate(start)
        response = TestClient(api).post(
            "/users/v1/genders/",
            json={"name": ""},
            headers={"Authorization": f"Bearer {token._raw_token}", **headers},
        )
        assert response.status_code == 422
        return response.json()["detail"]

    def test_a_validation_error_comes_back_in_english(self):
        assert self._blank_gender(start=OTHER) == [BLANK]

    def test_a_validation_error_comes_back_in_the_language_asked_for(self):
        with translation.override(OTHER):
            asked = str(BLANK_LAZY)
        assert asked != BLANK
        assert self._blank_gender(start="en", **{"Accept-Language": OTHER}) == [asked]


def test_the_schema_reads_the_same_in_every_language():
    # Agents read the schema to phrase their requests; it is the contract.
    # This held before the rule too: it guards the contract, not the rule.
    with translation.override("en"):
        english = api.get_openapi_schema(path_prefix="")
    with translation.override(OTHER):
        assert api.get_openapi_schema(path_prefix="") == english
