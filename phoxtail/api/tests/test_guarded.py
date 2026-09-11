"""`guarded()` asks both halves of authorization about one codename.

A credential can only ever narrow its owner. `has_scope` enforces the
narrowing; `has_permission` establishes there was something to narrow. An
endpoint that asked only the first would let a token *grant* a codename
its owner was never allowed — which is possible, because minting a token
deliberately does not require holding what it names.

The two refusals are kept apart on purpose. "Widen your token" and "ask an
administrator" are different instructions to different people.
"""

from __future__ import annotations

import pytest
from django.contrib.auth.models import Permission
from ninja.errors import HttpError

from phoxtail.api.auth import (
    Authorize,
    PhoxtailSessionAuth,
    Refused,
    guarded,
    has_permission,
)
from phoxtail.core.authorization import AuthorizationContext
from phoxtail.tokens.ninja import PhoxtailTokenAuth

CODENAME = "phoxtail_dashboard.change_menu"
OTHER = "phoxtail_dashboard.delete_menu"


@pytest.fixture
def editor(db, django_user_model):
    """An account holding `change_menu` and nothing else."""
    user = django_user_model.objects.create_user(username="guarded-editor", email="editor@example.invalid")
    user.user_permissions.add(
        Permission.objects.get(content_type__app_label="phoxtail_dashboard", codename="change_menu")
    )
    return django_user_model.objects.get(pk=user.pk)


@pytest.fixture
def outsider(db, django_user_model):
    return django_user_model.objects.create_user(username="guarded-outsider", email="outsider@example.invalid")


def _token(*scopes, unrestricted=False):
    class _Token:
        pass

    token = _Token()
    token.scopes = list(scopes)
    token.unrestricted = unrestricted
    return token


def _run(codenames, context):
    """Apply the predicate the way `Authorize` does."""
    predicate = guarded(*codenames)[0].predicate
    return predicate(context)


class TestBothHalves:
    def test_permitted_person_with_an_unrestricted_token_passes(self, editor):
        assert _run([CODENAME], AuthorizationContext(user=editor, token=_token(unrestricted=True)))

    def test_permitted_person_in_a_browser_session_passes(self, editor):
        """A session has no credential to narrow by."""
        assert _run([CODENAME], AuthorizationContext(user=editor))

    def test_permitted_person_with_a_matching_scope_passes(self, editor):
        assert _run([CODENAME], AuthorizationContext(user=editor, token=_token(CODENAME)))

    def test_a_narrower_token_refuses_a_permitted_person(self, editor):
        """The system working: the key was deliberately limited."""
        with pytest.raises(Refused) as refusal:
            _run([CODENAME], AuthorizationContext(user=editor, token=_token(OTHER)))
        assert "token's scopes" in str(refusal.value)

    def test_a_token_cannot_grant_what_its_owner_lacks(self, outsider):
        """The case the person-half exists for.

        The key names the codename. Its owner never held it. Without this,
        the scope would be the only thing in the way — and a scope that
        grants is not a ceiling.
        """
        with pytest.raises(Refused) as refusal:
            _run([CODENAME], AuthorizationContext(user=outsider, token=_token(CODENAME)))
        assert "does not have permission" in str(refusal.value)

    def test_an_unrestricted_token_cannot_grant_it_either(self, outsider):
        with pytest.raises(Refused):
            _run([CODENAME], AuthorizationContext(user=outsider, token=_token(unrestricted=True)))

    def test_every_codename_is_required(self, editor):
        """A partial match is a refusal: the endpoint declared what it needs."""
        with pytest.raises(Refused):
            _run([CODENAME, OTHER], AuthorizationContext(user=editor, token=_token(unrestricted=True)))


class TestTheTwoRefusalsAreDistinguishable:
    """One message for both would tell the wrong person to act."""

    def test_the_person_refusal_names_the_codename(self, outsider):
        with pytest.raises(Refused) as refusal:
            _run([CODENAME], AuthorizationContext(user=outsider, token=_token(unrestricted=True)))
        assert CODENAME in str(refusal.value)

    def test_the_credential_refusal_names_the_codename(self, editor):
        with pytest.raises(Refused) as refusal:
            _run([CODENAME], AuthorizationContext(user=editor, token=_token()))
        assert CODENAME in str(refusal.value)

    def test_they_do_not_read_the_same(self, editor, outsider):
        with pytest.raises(Refused) as person:
            _run([CODENAME], AuthorizationContext(user=outsider, token=_token(unrestricted=True)))
        with pytest.raises(Refused) as credential:
            _run([CODENAME], AuthorizationContext(user=editor, token=_token()))
        assert str(person.value) != str(credential.value)


class TestHasPermission:
    def test_a_superuser_holds_everything(self, db, django_user_model):
        admin = django_user_model.objects.create_superuser(
            username="guarded-admin", email="admin@example.invalid", password="x"
        )
        assert has_permission(CODENAME, OTHER)(AuthorizationContext(user=admin))

    def test_a_deactivated_account_holds_nothing(self, editor):
        editor.is_active = False
        assert not has_permission(CODENAME)(AuthorizationContext(user=editor))


class TestAuthorizeTurnsItIntoA403:
    """The wrapper is where `Refused` becomes an HTTP answer."""

    def test_the_predicates_words_reach_the_caller(self, outsider):
        context = AuthorizationContext(user=outsider, token=_token(unrestricted=True))
        # A stub authenticator, so the wrapper's own behaviour is what is
        # under test rather than either real backend.
        wrapper = Authorize(lambda request: context, guarded(CODENAME)[0].predicate)

        with pytest.raises(HttpError) as response:
            wrapper(object())

        assert response.value.status_code == 403
        assert "does not have permission" in response.value.message

    def test_an_unauthenticated_caller_is_not_forbidden(self):
        """Returning None lets ninja try the next backend, then answer 401."""
        wrapper = Authorize(lambda request: None, guarded(CODENAME)[0].predicate)
        assert wrapper(object()) is None


class TestTheStackItBuilds:
    """Both backends, or a browser session silently stops being served.

    The predicate is the interesting part and every test above reaches it
    directly — which is exactly why the shape needs asserting somewhere:
    drop the session entry and nothing else here would notice.
    """

    def test_it_wraps_both_authenticators(self):
        stack = guarded(CODENAME)
        assert [type(wrapper.authenticator) for wrapper in stack] == [
            PhoxtailTokenAuth,
            PhoxtailSessionAuth,
        ]

    def test_every_entry_asks_the_same_question(self, outsider):
        """One predicate, so the two paths cannot drift apart."""
        for wrapper in guarded(CODENAME):
            with pytest.raises(Refused):
                wrapper.predicate(AuthorizationContext(user=outsider))
