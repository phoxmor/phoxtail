"""Tests for the verify_email management command.

The command lives in the project template, so we test it with mocked
Django/allauth dependencies rather than a full Django test harness.
"""

from io import StringIO
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


@pytest.fixture(autouse=True)
def _stub_django(monkeypatch):
    """Provide minimal stubs so the command module can be imported."""
    import sys

    # Stub django modules
    django_auth = MagicMock()
    django_base = MagicMock()
    django_conf = MagicMock()
    allauth_models = MagicMock()

    stubs = {
        "django": MagicMock(),
        "django.contrib": MagicMock(),
        "django.contrib.auth": django_auth,
        "django.core": MagicMock(),
        "django.core.management": MagicMock(),
        "django.core.management.base": django_base,
        "django.conf": django_conf,
        "allauth": MagicMock(),
        "allauth.account": MagicMock(),
        "allauth.account.models": allauth_models,
    }

    # BaseCommand needs to be a real-ish class
    class FakeBaseCommand:
        def __init__(self):
            self.stdout = StringIO()
            self.stderr = StringIO()
            self.style = SimpleNamespace(
                SUCCESS=lambda x: f"SUCCESS: {x}",
                WARNING=lambda x: f"WARNING: {x}",
                ERROR=lambda x: f"ERROR: {x}",
            )

    django_base.BaseCommand = FakeBaseCommand

    saved = {}
    for mod_name, stub in stubs.items():
        saved[mod_name] = sys.modules.get(mod_name)
        sys.modules[mod_name] = stub

    yield SimpleNamespace(
        get_user_model=django_auth.get_user_model,
        EmailAddress=allauth_models.EmailAddress,
    )

    for mod_name, original in saved.items():
        if original is None:
            sys.modules.pop(mod_name, None)
        else:
            sys.modules[mod_name] = original


def _load_command():
    """Import the Command class fresh (after stubs are in place)."""
    import importlib
    import sys

    mod_path = "phoxtail.users.management.commands.verify_email"
    sys.modules.pop(mod_path, None)
    mod = importlib.import_module(mod_path)
    return mod.Command


def _make_user(email="admin@example.com", is_superuser=False, status="verified"):
    user = MagicMock()
    user.email = email
    user.is_superuser = is_superuser
    # The command delegates the allauth record work to the service layer
    # (UserService.admin.verify_email) and only renders its status.
    user.service.admin.verify_email.return_value = status
    return user


class TestVerifyEmailDirect:
    """Test verify_email with a specific email argument."""

    def test_verifies_existing_user(self, _stub_django):
        Command = _load_command()
        user = _make_user("test@example.com")
        User = _stub_django.get_user_model.return_value
        User.objects.get.return_value = user

        cmd = Command()
        cmd.handle(email="test@example.com", all_superusers=False)

        User.objects.get.assert_called_once_with(email="test@example.com")
        user.service.admin.verify_email.assert_called_once_with()
        assert "Verified: test@example.com" in cmd.stdout.getvalue()

    def test_user_not_found_exits(self, _stub_django):
        Command = _load_command()
        from django.contrib.auth import get_user_model

        User = get_user_model.return_value
        User.DoesNotExist = type("DoesNotExist", (Exception,), {})
        User.objects.get.side_effect = User.DoesNotExist

        cmd = Command()
        with pytest.raises(SystemExit):
            cmd.handle(email="missing@example.com", all_superusers=False)

        assert "No user found" in cmd.stderr.getvalue()

    def test_already_verified_reports_status(self, _stub_django):
        Command = _load_command()
        user = _make_user("admin@example.com", status="already_verified")
        User = _stub_django.get_user_model.return_value
        User.objects.get.return_value = user

        cmd = Command()
        cmd.handle(email="admin@example.com", all_superusers=False)

        assert "Already verified: admin@example.com" in cmd.stdout.getvalue()

    def test_no_email_no_flag_exits(self, _stub_django):
        Command = _load_command()

        cmd = Command()
        with pytest.raises(SystemExit):
            cmd.handle(email=None, all_superusers=False)

        assert "Provide an email" in cmd.stderr.getvalue()


class TestVerifyEmailAllSuperusers:
    """Test --all-superusers flag."""

    def test_verifies_all_superusers(self, _stub_django):
        Command = _load_command()
        users = [
            _make_user("admin1@example.com", is_superuser=True),
            _make_user("admin2@example.com", is_superuser=True),
        ]
        qs = MagicMock()
        User = _stub_django.get_user_model.return_value
        User.objects.filter.return_value.exclude.return_value = qs
        qs.exists.return_value = True
        qs.__iter__ = lambda self: iter(users)

        cmd = Command()
        cmd.handle(email=None, all_superusers=True)

        for user in users:
            user.service.admin.verify_email.assert_called_once_with()
        assert "Verified: admin1@example.com" in cmd.stdout.getvalue()
        assert "Verified: admin2@example.com" in cmd.stdout.getvalue()

    def test_no_superusers_warns(self, _stub_django):
        Command = _load_command()
        qs = MagicMock()
        User = _stub_django.get_user_model.return_value
        User.objects.filter.return_value.exclude.return_value = qs
        qs.exists.return_value = False

        cmd = Command()
        cmd.handle(email=None, all_superusers=True)

        assert "No superusers" in cmd.stderr.getvalue()
