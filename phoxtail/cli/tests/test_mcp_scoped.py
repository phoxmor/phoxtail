"""A tool is offered only to a credential permitting acts of its kind.

``scoped()`` is the check an annotated tool names. It answers the
credential's half of the question — and only that half: the endpoint the
tool reaches asks it again, alongside whether the *person* may act.

Two properties are asserted here that a plain predicate would not have.
An unrestricted token carries an empty scope list and must still pass,
because the flag is the ceiling's absence rather than a ceiling of
nothing. And the check stays *scope-aware*, so a denial can name what is
missing instead of being an opaque no — which is what the last class
guards, against the library rather than against us.
"""

from __future__ import annotations

from types import SimpleNamespace

from fastmcp.utilities.authorization import scope_requirements

from phoxtail.mcp.authorization import local_only, scoped

PUBLISH = "wagtailcore.publish_page"
EDIT = "phoxtail_streams.change_blockvariant"


def _ctx(token):
    """An auth context naming no component in particular.

    Every check here reads the token alone, so the component is only the
    dataclass field ``scope_requirements`` needs to exist.
    """
    return SimpleNamespace(token=token, component=SimpleNamespace(tags=set()))


def _token(*scopes, unrestricted=False):
    return SimpleNamespace(
        scopes=list(scopes),
        claims={"unrestricted": unrestricted, "is_superuser": False},
    )


class TestTheCheck:
    def test_admits_a_token_naming_the_codename(self):
        assert scoped(PUBLISH)(_ctx(_token(PUBLISH))) is True

    def test_refuses_a_token_that_does_not(self):
        assert scoped(PUBLISH)(_ctx(_token(EDIT))) is False

    def test_every_codename_is_required(self):
        """A partial match is a refusal: the tool declared what it needs."""
        assert scoped(PUBLISH, EDIT)(_ctx(_token(PUBLISH))) is False
        assert scoped(PUBLISH, EDIT)(_ctx(_token(PUBLISH, EDIT))) is True

    def test_admits_an_unrestricted_token_holding_no_scopes(self):
        """The flag is the absence of a ceiling, not a ceiling of nothing."""
        assert scoped(PUBLISH)(_ctx(_token(unrestricted=True))) is True

    def test_refuses_a_caller_with_no_token(self):
        assert scoped(PUBLISH)(_ctx(None)) is False

    def test_being_a_superuser_does_not_widen_a_scoped_token(self):
        """A limited key is limited whoever owns it."""
        admin = SimpleNamespace(scopes=[EDIT], claims={"unrestricted": False, "is_superuser": True})
        assert scoped(PUBLISH)(_ctx(admin)) is False


class TestTheShortfall:
    """What a denial can name, which is the reason for the subclass."""

    def test_names_what_a_scoped_token_lacks(self):
        assert scoped(PUBLISH, EDIT).missing_scopes(_ctx(_token(PUBLISH))) == {EDIT}

    def test_names_nothing_when_satisfied(self):
        assert scoped(PUBLISH).missing_scopes(_ctx(_token(PUBLISH))) == set()

    def test_names_nothing_for_an_unrestricted_token(self):
        """The credential that has no ceiling has no shortfall either.

        Left to the inherited comparison this would report every codename
        as missing for a caller it had just admitted — the token's scopes
        are empty — and ``scope_requirements`` reads it without running
        the check that would have passed.
        """
        assert scoped(PUBLISH, EDIT).missing_scopes(_ctx(_token(unrestricted=True))) == set()

    def test_an_absent_token_is_not_a_shortfall(self):
        """Nothing to re-authorize for: that caller has yet to authenticate."""
        assert scoped(PUBLISH).missing_scopes(_ctx(None)) == set()


class TestTheLibrarySeam:
    """The canary for depending on fastmcp's scope-aware base class.

    ``scope_requirements`` recognises a scope-aware check by ``isinstance``
    against a private base, so duck-typing ``missing_scopes`` would not do.
    If a future fastmcp moves or restructures that base, this is where it
    is noticed — as a failure naming the reason, rather than as tools that
    quietly deny without saying why.
    """

    def test_the_shortfall_survives_the_library(self):
        assert scope_requirements([scoped(PUBLISH, EDIT)], _ctx(_token(PUBLISH))) == [EDIT]

    def test_an_opaque_sibling_withholds_the_whole_list(self):
        """``local_only`` denies for a reason no scope would fix.

        Its presence must silence the shortfall entirely — a caller
        blocked by the transport must not be told to go obtain a scope
        that would not help, nor that the component exists at all.
        """
        assert scope_requirements([local_only, scoped(PUBLISH)], _ctx(_token())) is None
