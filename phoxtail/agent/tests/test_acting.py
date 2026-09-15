"""A chat turn acts as the person chatting, with a credential of their own.

Before this, a turn was a person Django knew and every door met as a
stranger. Tools called the API with the credential stored on the machine,
so everyone's work was attributed to the operator; and the tool registry,
asked what a caller with no credential may be offered, answered with the
handful of tools that name no permission — so the catalogue collapsed for
everyone at once.

Both symptoms are one absence, which is why these tests assert both from
the same fixture: the token that goes out, and the catalogue that comes
back.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from uuid import uuid4

import pytest
from asgiref.sync import sync_to_async
from django.contrib.auth.models import Group, Permission

from phoxtail.agent.acting import (
    acting_as,
    mint_turn_credential,
    revoke_turn_credential,
)
from phoxtail.mcp._http import outbound_token
from phoxtail.tokens.constants import TokenType
from phoxtail.tokens.models import AccessToken

pytestmark = pytest.mark.django_db


PROVIDERS = "phoxtail_agent.view_inferenceprovider"


@pytest.fixture
def reader(django_user_model):
    """Someone who may do exactly one thing."""
    user = django_user_model.objects.create_user(username="reader", email="reader@example.invalid", password="x")
    group = Group.objects.create(name="readers")
    group.permissions.add(
        Permission.objects.get(
            content_type__app_label="phoxtail_agent",
            codename="view_inferenceprovider",
        )
    )
    user.groups.add(group)
    # Permissions are cached on the instance at first use; re-fetch so the
    # grant above is the one under test rather than an empty cache.
    return django_user_model.objects.get(pk=user.pk)


class TestTheCredential:
    """What a turn's credential is, asked of the function that decides.

    Synchronous on purpose: minting is a decision about scopes, lifetime
    and ownership, and none of that needs an event loop. The plumbing that
    awaits it is tested separately, below.
    """

    def test_it_belongs_to_the_person_chatting(self, reader):
        token, raw = mint_turn_credential(reader)
        assert token.user == reader
        assert raw

    def test_it_is_marked_as_the_channel_that_holds_it(self, reader):
        token, _ = mint_turn_credential(reader)
        assert token.token_type == TokenType.CHATBOT

    def test_it_carries_the_persons_own_permissions(self, reader):
        token, _ = mint_turn_credential(reader)
        assert token.scopes == [PROVIDERS]

    def test_it_is_never_unrestricted(self, reader):
        """A ceiling written at mint time, not a flag that rises later.

        ``unrestricted`` means *whatever its owner may do, including what
        is installed tomorrow*. A credential that lives for one exchange
        has no tomorrow, and the flag would reintroduce the wildcard this
        project removed.
        """
        token, _ = mint_turn_credential(reader)
        assert token.unrestricted is False

    def test_it_expires(self, reader):
        token, _ = mint_turn_credential(reader)
        assert token.expires_at is not None

    def test_revoking_it_takes_it_out_of_use(self, reader):
        token, _ = mint_turn_credential(reader)
        revoke_turn_credential(token)
        assert AccessToken.objects.get(pk=token.pk).revoked_at is not None


class TestTheTurn:
    """The plumbing: what a turn puts the credential into, and takes out.

    Minting is stubbed here, deliberately. These assert that a turn sets
    the credential where the two readers look and clears it afterwards —
    which is a statement about context, not about tokens, and testing it
    against a real database would only add a thread between the assertion
    and the thing asserted.
    """

    @pytest.fixture
    def turn(self, monkeypatch):
        """``acting_as`` with minting and revoking replaced."""
        revoked = []

        class _Token:
            pk = 1
            scopes: list[str] = []
            unrestricted = False
            expires_at = None

            class user:
                email = "reader@example.invalid"
                uuid = uuid4()
                is_superuser = False

        def mint(user):
            return _Token(), f"phxt_for_{user}"

        monkeypatch.setattr("phoxtail.agent.acting._amint", sync_to_async(mint))
        monkeypatch.setattr("phoxtail.agent.acting._arevoke", sync_to_async(revoked.append))
        return SimpleNamespace(revoked=revoked)

    def test_the_call_goes_out_as_the_person(self, turn):
        """The whole point, and the thing that was silently wrong.

        Outside a turn ``outbound_token`` answers with the machine's
        stored credential. Inside one it must answer with this person's,
        or every chat user acts as whoever ran ``phoxtail auth login``.
        """

        async def go():
            async with acting_as("alice"):
                return outbound_token()

        assert asyncio.run(go()) == "phxt_for_alice"

    def test_the_catalogue_is_asked_as_the_person_too(self, turn):
        """Two readers, one credential, and neither can see the other.

        The tool registry does not call ``outbound_token``; it asks the
        MCP SDK for the credential of the caller being served. Setting one
        and not the other is the failure this pins — the calls would go
        out as the person while the tool list stayed somebody else's.
        """
        from fastmcp.server.dependencies import get_access_token

        async def go():
            async with acting_as("alice"):
                return get_access_token()

        assert asyncio.run(go()) is not None

    def test_both_are_cleared_afterwards(self, turn, monkeypatch):
        from fastmcp.server.dependencies import get_access_token

        monkeypatch.setattr("phoxtail.mcp._http.resolve_token", lambda *a, **k: "phxt_ambient")

        async def go():
            async with acting_as("alice"):
                pass
            return outbound_token(), get_access_token()

        sent, seen = asyncio.run(go())
        assert sent == "phxt_ambient"
        assert seen is None

    def test_it_is_revoked_when_the_turn_fails(self, turn):
        """A turn that raises must not leave a usable credential behind.

        The short life is the whole of the protection, and a credential
        that outlives the exchange it was minted for is not short-lived.
        """

        async def go():
            async with acting_as("alice"):
                raise ValueError("the model fell over")

        with pytest.raises(ValueError):
            asyncio.run(go())
        assert len(turn.revoked) == 1

    def test_two_turns_do_not_see_each_others_credential(self, turn):
        """Two people chatting at once, in one process.

        The credential travels in context variables rather than module
        globals for exactly this reason. If they shared one, the failure
        would be one person acting as another — silently, and only under
        load.
        """
        seen = {}

        async def one(name, mine, theirs):
            async with acting_as(name):
                theirs.set()
                await mine.wait()
                seen[name] = outbound_token()

        async def both():
            a, b = asyncio.Event(), asyncio.Event()
            await asyncio.gather(one("alice", a, b), one("bob", b, a))

        asyncio.run(both())
        assert seen == {"alice": "phxt_for_alice", "bob": "phxt_for_bob"}


class TestOutsideATurn:
    def test_the_ambient_credential_still_answers(self, monkeypatch):
        """A local shell session must keep behaving as it did.

        The third case is additive: it answers only while somebody is
        acting, and leaves the other two exactly as they were.
        """
        monkeypatch.setattr("phoxtail.mcp._http.resolve_token", lambda *a, **k: "phxt_ambient")
        assert outbound_token() == "phxt_ambient"


class TestTheCatalogueFollowsThePerson:
    """The acceptance test: two people, two different tool lists.

    Everything above tests a part. This tests the point — that what the
    chatbot is offered is a fact about whoever is chatting, which is the
    property the whole change exists to produce and the one a future
    refactor would undo without failing anything else.

    Deliberately not driven through ``acting_as``: that mints through
    ``sync_to_async``, which runs the ORM on another thread, and the test
    database is in-memory SQLite — a second connection is a second, empty
    database. Minting is a plain function, so the test does the two steps
    itself and asserts the thing that matters rather than the plumbing
    around it. ``test_the_catalogue_is_asked_as_the_person_too`` covers
    that ``acting_as`` performs the second step at all.
    """

    @staticmethod
    def _offered_to(user):
        from mcp.server.auth.middleware.auth_context import (
            AuthenticatedUser,
            auth_context_var,
        )

        from phoxtail.agent.tools import tools_for_caller
        from phoxtail.mcp.authorization import as_access_token

        token, raw = mint_turn_credential(user)
        reset = auth_context_var.set(AuthenticatedUser(as_access_token(raw, token)))
        try:
            return sorted(t.name for t in asyncio.run(tools_for_caller()))
        finally:
            auth_context_var.reset(reset)
            revoke_turn_credential(token)

    def test_a_narrow_person_is_offered_less_than_a_broad_one(self, reader, django_user_model):
        boss = django_user_model.objects.create_superuser(username="boss", email="boss@example.invalid", password="x")
        narrow = self._offered_to(reader)
        broad = self._offered_to(boss)

        assert len(narrow) < len(broad)
        # Not merely fewer: the tools the reader's one permission covers
        # are there, and the ones it does not are not.
        assert "phoxtail_agent_list_providers" in narrow
        assert "phoxtail_users_list_users" not in narrow
        assert "phoxtail_users_list_users" in broad

    def test_the_tools_asking_for_nothing_survive_a_narrow_ceiling(self, reader):
        """A catalogue that empties would be a different failure.

        Tools naming no codename ask the credential for nothing, so they
        survive any ceiling — which is what keeps an agent able to orient
        itself with a credential that covers almost nothing.
        """
        assert "phoxtail_page_types_list" in self._offered_to(reader)

    def test_a_person_holding_nothing_cannot_be_minted_a_credential(self, django_user_model):
        """The boundary, asserted rather than discovered later.

        A token must name a ceiling or declare it has none, so there is no
        way to write down "permitted nothing" — deliberately: every other
        caller of the mint service would otherwise create an unlimited
        token by omission.

        Unreachable from a chat turn, because reaching one requires
        ``access_chatbot`` and that is itself a permission, so anyone who
        gets this far holds at least one. Pinned because the safety comes
        from a check in a different app, and the failure if it ever moved
        would be a turn dying at its first line.
        """
        from django.core.exceptions import ValidationError

        nobody = django_user_model.objects.create_user(username="nobody", email="nobody@example.invalid", password="x")
        assert nobody.get_all_permissions() == set()
        with pytest.raises(ValidationError):
            mint_turn_credential(nobody)
