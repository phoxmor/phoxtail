"""Dead token rows are removed after their retention, and only those."""

from datetime import timedelta

import pytest
from django.core.management import call_command
from django.utils import timezone
from oauth2_provider.models import AccessToken as ServerToken
from oauth2_provider.models import Application

from phoxtail.tokens.models import AccessToken

from .factories import AccessTokenFactory, UserFactory

DAY = timedelta(days=1)


def _token(**fields):
    return AccessTokenFactory(**fields)


@pytest.mark.django_db
class TestPhoxtailsOwnRows:
    def test_only_dead_rows_past_retention_go(self):
        from phoxtail.tokens.sweep import sweep

        now = timezone.now()
        alive = _token()
        revoked_recently = _token(revoked_at=now - 10 * DAY)
        revoked_long_ago = _token(revoked_at=now - 91 * DAY)
        expired_long_ago = _token(expires_at=now - 91 * DAY)
        expired_recently = _token(expires_at=now - 1 * DAY)

        assert sweep()["phoxtail"] == 2
        kept = set(AccessToken.objects.values_list("pk", flat=True))
        assert kept == {alive.pk, revoked_recently.pk, expired_recently.pk}
        assert revoked_long_ago.pk not in kept and expired_long_ago.pk not in kept

    def test_a_chat_turn_credential_is_kept_while_it_can_act_and_swept_when_old(self):
        """The family this exists for: every chat turn mints a fifteen-minute
        token, scoped, revoked on the way out. One mid-turn is live; one
        revoked yesterday is evidence; one from last quarter is gone."""
        from phoxtail.tokens.constants import TokenType
        from phoxtail.tokens.sweep import sweep

        now = timezone.now()
        turn = dict(token_type=TokenType.CHATBOT, unrestricted=False, scopes=["wagtailcore.view_page"])
        mid_turn = _token(**turn, expires_at=now + timedelta(minutes=15))
        yesterday = _token(**turn, expires_at=now - DAY, revoked_at=now - DAY)
        last_quarter = _token(**turn, expires_at=now - 100 * DAY, revoked_at=now - 100 * DAY)
        # A turn that crashed before revoking: expired, never revoked, old.
        crashed_long_ago = _token(**turn, expires_at=now - 100 * DAY)

        assert sweep()["phoxtail"] == 2
        kept = set(AccessToken.objects.values_list("pk", flat=True))
        assert kept == {mid_turn.pk, yesterday.pk}
        assert last_quarter.pk not in kept and crashed_long_ago.pk not in kept

    def test_a_key_with_no_expiry_lives_until_revoked(self):
        from phoxtail.tokens.sweep import sweep

        forever = _token(expires_at=None)
        assert sweep()["phoxtail"] == 0
        assert AccessToken.objects.filter(pk=forever.pk).exists()

    def test_retention_is_a_parameter(self):
        from phoxtail.tokens.sweep import sweep

        _token(revoked_at=timezone.now() - 10 * DAY)
        assert sweep(retention_days=30)["phoxtail"] == 0
        assert sweep(retention_days=7)["phoxtail"] == 1

    def test_running_twice_removes_nothing_the_second_time(self):
        from phoxtail.tokens.sweep import sweep

        _token(revoked_at=timezone.now() - 100 * DAY)
        assert sweep()["phoxtail"] == 1
        assert sweep()["phoxtail"] == 0


@pytest.mark.django_db
class TestTheServersRowsGoToo:
    def test_an_expired_server_token_is_removed(self):
        from phoxtail.tokens.sweep import sweep

        app = Application.objects.create(
            user=UserFactory(),
            client_type=Application.CLIENT_PUBLIC,
            authorization_grant_type=Application.GRANT_AUTHORIZATION_CODE,
            name="x",
        )
        ServerToken.objects.create(
            user=app.user, application=app, token="dead", expires=timezone.now() - DAY, scope="read"
        )
        ServerToken.objects.create(
            user=app.user, application=app, token="live", expires=timezone.now() + DAY, scope="read"
        )
        assert sweep()["server"] == 1
        assert list(ServerToken.objects.values_list("token", flat=True)) == ["live"]


@pytest.mark.django_db
def test_the_command_reports_what_it_did(capsys):
    _token(revoked_at=timezone.now() - 100 * DAY)
    call_command("sweeptokens")
    assert "Removed 1" in capsys.readouterr().out
