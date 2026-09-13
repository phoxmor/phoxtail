"""What each cms endpoint asks of its caller.

This commit covers only ``page-types``, which asks for nothing — and the
interesting part is that saying so takes an annotation rather than silence.
The families that do name codenames follow.

``TestNarrowedTokens`` is the part worth copying forward. Every per-domain
auth test in this workstream authenticates through ``PhoxtailSessionAuth``,
where ``token`` is ``None`` and the credential half of the question is
answered "no ceiling" before it is really asked. That makes a session test
blind to whether a *narrowed* credential can reach an endpoint at all — which
is how a door shut to every scoped token in the project passed a full suite.
"""

from __future__ import annotations


class TestPageTypes:
    """Deliberately open — and open to narrowed tokens too, which is the part
    that does not come for free."""

    def test_any_authenticated_caller_may_read_the_catalogue(self, raw_client, regular_user):
        """It lists page type and field *names* from installed code.

        No rows, no content, and no permission naming it. An agent reads it
        before it can phrase a request at all; the content behind those types
        is a separate question the pages endpoints answer per subtree.
        """
        assert raw_client.get("/cms/v1/page-types/", user=regular_user).status_code == 200

    def test_it_is_still_closed_to_nobody(self, db, raw_client):
        """``authenticated()`` is not ``auth=None`` — anonymous is still 401."""
        assert raw_client.get("/cms/v1/page-types/").status_code == 401

    def test_a_narrowed_token_can_still_read_it(self, raw_client, regular_user, scoped_token):
        """The reason it carries ``authenticated()`` instead of nothing.

        A token minted to let an agent create pages must be able to read the
        field list first, or the workflow dies at its discovery step. Left
        bare, this endpoint would keep the API-wide default and refuse every
        narrowed credential in the project — while every session-based test
        beside it carried on passing.
        """
        headers = scoped_token(regular_user, "wagtailcore.add_page")
        assert raw_client.get("/cms/v1/page-types/", headers=headers).status_code == 200

    def test_a_token_narrowed_to_something_unrelated_can_read_it_too(self, raw_client, regular_user, scoped_token):
        """There is no codename behind this, so no token is the wrong token."""
        headers = scoped_token(regular_user, "phoxtail_streams.view_block")
        assert raw_client.get("/cms/v1/page-types/", headers=headers).status_code == 200

    def test_the_tool_that_calls_it_names_nothing_either(self):
        """Both halves agree, so a narrowed token is neither lied to nor
        withheld from.

        The two defaults are opposites — an endpoint naming nothing is closed
        to scoped tokens, a tool naming nothing is offered to all — so the
        pair only tells the truth when the endpoint says "open" out loud.
        """
        from phoxtail.cms.mcp import resources

        assert getattr(resources.page_types_list, "auth", None) in (None, [])


class TestNarrowedTokens:
    """That the fixture mints something genuinely narrowed.

    Without this the tests above would pass with a fixture that quietly
    handed back an unrestricted token, which is exactly the failure mode
    they exist to rule out.
    """

    def test_the_minted_token_really_carries_a_ceiling(self, db, regular_user, scoped_token):
        from phoxtail.api.auth import has_no_ceiling
        from phoxtail.core.authorization import AuthorizationContext
        from phoxtail.tokens.models import AccessToken

        scoped_token(regular_user, "wagtailcore.add_page")
        token = AccessToken.objects.filter(user=regular_user).latest("created_at")
        assert token.unrestricted is False
        assert token.scopes == ["wagtailcore.add_page"]
        assert has_no_ceiling(AuthorizationContext(user=regular_user, token=token)) is False

    def test_an_unannotated_endpoint_would_refuse_it(self, raw_client, regular_user, scoped_token):
        """The default this commit works around, asserted rather than assumed.

        ``/collections/`` has not been annotated yet, so it still carries the
        API-wide default — and that default is what would have shut
        ``page-types`` to every narrowed credential.
        """
        headers = scoped_token(regular_user, "wagtailcore.add_page")
        assert raw_client.get("/cms/v1/collections/", headers=headers).status_code == 403
