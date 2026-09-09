import hashlib
import re
from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from phoxtail.tokens.constants import TokenType
from phoxtail.tokens.models import AccessToken
from phoxtail.tokens.services import AccessTokenService

pytestmark = pytest.mark.django_db


class TestCreateValidation:
    @pytest.mark.parametrize("name", ["", "   ", "\t\n"])
    def test_blank_name_raises(self, user, name):
        with pytest.raises(ValidationError) as exc:
            AccessTokenService().admin.create(unrestricted=True, user_id=user.id, name=name)
        assert "name" in exc.value.message_dict

    def test_empty_scopes_without_unrestricted_raises(self, user):
        with pytest.raises(ValidationError) as exc:
            AccessTokenService().admin.create(user_id=user.id, name="t", scopes=[])
        assert "scopes" in exc.value.message_dict

    def test_unrestricted_with_scopes_raises(self, user):
        """A ceiling and "no ceiling" together is a contradiction, and
        silently honouring one of them would mislead whoever reads the
        token later."""
        with pytest.raises(ValidationError) as exc:
            AccessTokenService().admin.create(user_id=user.id, name="t", scopes=[REAL_SCOPE], unrestricted=True)
        assert "scopes" in exc.value.message_dict

    def test_unrestricted_without_scopes_is_allowed(self, user):
        token, _ = AccessTokenService().admin.create(user_id=user.id, name="t", unrestricted=True)
        assert token.unrestricted is True
        assert token.scopes == []

    def test_non_list_scopes_raises(self, user):
        with pytest.raises(ValidationError):
            AccessTokenService().admin.create(user_id=user.id, name="t", scopes="*")

    @pytest.mark.parametrize("bad", [[""], [None], [1], ["valid", ""]])
    def test_invalid_scope_entries_raise(self, user, bad):
        with pytest.raises(ValidationError) as exc:
            AccessTokenService().admin.create(user_id=user.id, name="t", scopes=bad)
        assert "scopes" in exc.value.message_dict

    def test_past_expiry_raises(self, user):
        with pytest.raises(ValidationError) as exc:
            AccessTokenService().admin.create(
                user_id=user.id,
                name="t",
                unrestricted=True,
                expires_at=timezone.now() - timedelta(seconds=1),
            )
        assert "expires_at" in exc.value.message_dict

    def test_now_expiry_raises(self, user):
        # Boundary: ``<=`` in validate, so equality must be rejected too.
        now = timezone.now()
        with pytest.raises(ValidationError):
            AccessTokenService().admin.create(unrestricted=True, user_id=user.id, name="t", expires_at=now)


class TestCreateDefaults:
    def test_scopes_default_empty_and_are_refused_alone(self, user):
        """Omitting scopes used to mint an unlimited token. Now it mints
        nothing: the caller must say which kind of token they want."""
        with pytest.raises(ValidationError) as exc:
            AccessTokenService().admin.create(user_id=user.id, name="t")
        assert "scopes" in exc.value.message_dict

    def test_unrestricted_defaults_off(self, user):
        token, _ = AccessTokenService().admin.create(user_id=user.id, name="t", scopes=[REAL_SCOPE])
        assert token.unrestricted is False

    def test_default_token_type_personal(self, user):
        token, _ = AccessTokenService().admin.create(unrestricted=True, user_id=user.id, name="t")
        assert token.token_type == TokenType.PERSONAL

    def test_explicit_token_type_overrides_default(self, user):
        token, _ = AccessTokenService().admin.create(
            unrestricted=True, user_id=user.id, name="t", token_type=TokenType.PERSONAL
        )
        assert token.token_type == TokenType.PERSONAL

    def test_name_is_stripped(self, user):
        token, _ = AccessTokenService().admin.create(unrestricted=True, user_id=user.id, name="  spaced  ")
        assert token.name == "spaced"

    def test_default_description_blank(self, user):
        token, _ = AccessTokenService().admin.create(unrestricted=True, user_id=user.id, name="t")
        assert token.description == ""


class TestRawTokenShape:
    def test_raw_token_starts_with_phxt_underscore(self, user):
        _, raw = AccessTokenService().admin.create(unrestricted=True, user_id=user.id, name="t")
        assert raw.startswith("phxt_")

    def test_raw_token_total_length(self, user):
        _, raw = AccessTokenService().admin.create(unrestricted=True, user_id=user.id, name="t")
        # "phxt_" (5) + 3 prefix + 32 body = 40
        assert len(raw) == 40

    def test_raw_token_is_alnum_in_random_section(self, user):
        _, raw = AccessTokenService().admin.create(unrestricted=True, user_id=user.id, name="t")
        # First 3 chars after "phxt_" are alnum; body is base64url
        assert re.match(r"^phxt_[A-Za-z0-9]{3}[A-Za-z0-9_\-]{32}$", raw)

    def test_each_call_produces_unique_raw_token(self, user):
        results = {
            AccessTokenService().admin.create(unrestricted=True, user_id=user.id, name=f"t{i}")[1] for i in range(20)
        }
        assert len(results) == 20

    def test_prefix_field_matches_first_8_of_raw(self, user):
        token, raw = AccessTokenService().admin.create(unrestricted=True, user_id=user.id, name="t")
        assert token.prefix == raw[:8]

    def test_suffix_field_matches_last_4_of_raw(self, user):
        token, raw = AccessTokenService().admin.create(unrestricted=True, user_id=user.id, name="t")
        assert token.suffix == raw[-4:]

    def test_digest_is_sha256_of_raw(self, user):
        token, raw = AccessTokenService().admin.create(unrestricted=True, user_id=user.id, name="t")
        assert token.digest == hashlib.sha256(raw.encode()).hexdigest()

    def test_raw_token_not_persisted_anywhere(self, user):
        token, raw = AccessTokenService().admin.create(unrestricted=True, user_id=user.id, name="t")
        # The raw secret body must never round-trip to the DB.
        body = raw[len("phxt_") + 3 :]
        token.refresh_from_db()
        assert body not in token.prefix
        assert body not in token.digest


class TestCreatePersistence:
    def test_creates_row(self, user):
        before = AccessToken.objects.count()
        AccessTokenService().admin.create(unrestricted=True, user_id=user.id, name="t")
        assert AccessToken.objects.count() == before + 1

    def test_assigns_user(self, user):
        token, _ = AccessTokenService().admin.create(unrestricted=True, user_id=user.id, name="t")
        assert token.user_id == user.id

    def test_unknown_user_raises(self, db):
        from django.contrib.auth import get_user_model

        with pytest.raises(get_user_model().DoesNotExist):
            AccessTokenService().admin.create(unrestricted=True, user_id=999_999, name="t")

    def test_passes_description_through(self, user):
        token, _ = AccessTokenService().admin.create(unrestricted=True, user_id=user.id, name="t", description="why")
        assert token.description == "why"

    def test_passes_future_expiry(self, user):
        when = timezone.now() + timedelta(days=7)
        token, _ = AccessTokenService().admin.create(unrestricted=True, user_id=user.id, name="t", expires_at=when)
        assert token.expires_at == when


REAL_SCOPE = "wagtailcore.publish_page"


class TestScopesMustNameRealPermissions:
    """A scope that matches nothing is not a smaller grant — it is a
    silent one. It stores cleanly and survives forever, and once
    enforcement lands the token quietly does less than whoever issued it
    believed, looking like a permissions problem rather than the typo it
    is. The only place it can still be caught is the door.
    """

    def test_a_real_permission_codename_is_accepted(self, user):
        token, _ = AccessTokenService().admin.create(user_id=user.id, name="t", scopes=[REAL_SCOPE])
        assert token.scopes == [REAL_SCOPE]

    def test_an_invented_scope_is_refused(self, user):
        with pytest.raises(ValidationError) as exc:
            AccessTokenService().admin.create(user_id=user.id, name="t", scopes=["nope.not_a_permission"])
        assert "scopes" in exc.value.message_dict

    def test_a_typo_is_refused_and_the_real_spelling_offered(self, user):
        """The reply to a near-miss is the correct spelling, not a
        restatement of the rule."""
        with pytest.raises(ValidationError) as exc:
            AccessTokenService().admin.create(user_id=user.id, name="t", scopes=["wagtailcore.publish_pge"])
        message = " ".join(exc.value.message_dict["scopes"])
        assert REAL_SCOPE in message

    def test_one_bad_scope_refuses_the_whole_token(self, user):
        """Partial acceptance would issue a credential that differs from
        the one that was asked for, silently."""
        with pytest.raises(ValidationError):
            AccessTokenService().admin.create(user_id=user.id, name="t", scopes=[REAL_SCOPE, "nope.not_a_permission"])
        assert not AccessToken.objects.filter(name="t").exists()

    def test_unrestricted_tokens_skip_the_check(self, user):
        """There are no scopes to validate, and requiring some would
        contradict what unrestricted means."""
        token, _ = AccessTokenService().admin.create(user_id=user.id, name="t", unrestricted=True)
        assert token.scopes == []
