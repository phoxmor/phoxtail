"""How ``phoxtail mcp serve`` finds the project it serves.

The tool surface is discovered from Django's app registry, so the server has
to load the project's settings before importing a single tool module. What it
must *not* do is ask for configuration of its own: every hatched project owns
its ``docker-compose.yaml``, so a new required variable would break each one on
its next restart with no way to fix it from the template.

So it makes the same two moves ``manage.py`` already makes. These tests pin
that, because the day they stop being true is the day existing projects stop
starting.
"""

from __future__ import annotations

import sys
from unittest.mock import patch

import pytest

from phoxtail.cli.mcp import _setup_django


@pytest.fixture
def project(tmp_path, monkeypatch):
    """A directory that looks like a phoxtail project, and is the cwd."""
    (tmp_path / "phoxtail.toml").write_text('[project]\nname = "x"\n')
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("DJANGO_SETTINGS_MODULE", raising=False)
    monkeypatch.delenv("DJANGO_ENV", raising=False)
    return tmp_path


class TestFindingTheSettings:
    def test_django_env_names_the_settings_module(self, project, monkeypatch):
        monkeypatch.setenv("DJANGO_ENV", "production")

        with patch("django.setup"):
            _setup_django()

        import os

        assert os.environ["DJANGO_SETTINGS_MODULE"] == "src.settings.production"

    def test_development_is_the_default(self, project):
        """Same default as manage.py, so an unset DJANGO_ENV means the same
        thing everywhere rather than only in the places that remember it."""
        with patch("django.setup"):
            _setup_django()

        import os

        assert os.environ["DJANGO_SETTINGS_MODULE"] == "src.settings.development"

    def test_an_explicit_settings_module_is_left_alone(self, project, monkeypatch):
        """An operator who has already answered keeps their answer."""
        monkeypatch.setenv("DJANGO_SETTINGS_MODULE", "someones.own.settings")
        monkeypatch.setenv("DJANGO_ENV", "production")

        with patch("django.setup"):
            _setup_django()

        import os

        assert os.environ["DJANGO_SETTINGS_MODULE"] == "someones.own.settings"


class TestFindingTheProject:
    def test_the_project_root_goes_on_the_path(self, project, monkeypatch):
        """Without this, ``src`` is not importable.

        A console script's ``sys.path[0]`` is the directory the script lives in
        — ``/usr/local/bin`` in the container — not the working directory. That
        is why manage.py, run as a file from the project root, never needed it.
        """
        monkeypatch.setattr(sys, "path", [p for p in sys.path if p != str(project)])

        with patch("django.setup"):
            _setup_django()

        assert sys.path[0] == str(project)

    def test_the_path_is_not_grown_on_every_call(self, project):
        with patch("django.setup"):
            _setup_django()
            _setup_django()

        assert sys.path.count(str(project)) == 1

    def test_no_project_in_scope_is_not_fatal_on_its_own(self, tmp_path, monkeypatch):
        """Django may still be configured from the environment.

        Refusing here would break a caller who set DJANGO_SETTINGS_MODULE and
        has the project on PYTHONPATH already — a legitimate way to run this.
        """
        monkeypatch.chdir(tmp_path)

        with patch("django.setup") as setup:
            _setup_django()

        assert setup.called


class TestWhenTheProjectCannotBeLoaded:
    def test_the_error_says_the_project_is_the_problem(self, project):
        """Django's own message names an environment variable and stops.

        The reader is running a server, not configuring Django: what they need
        to be told is that this command has to run where the project is.
        """
        import typer
        from django.core.exceptions import ImproperlyConfigured

        broken = ImproperlyConfigured("settings are not configured.")
        with patch("django.setup", side_effect=broken):
            with pytest.raises(typer.BadParameter) as exc:
                _setup_django()

        assert "project" in str(exc.value)
        assert "docker compose exec web phoxtail mcp serve" in str(exc.value)

    def test_a_broken_app_keeps_its_own_traceback(self, project):
        """Only "the project is not here" is rewritten.

        An app raising during setup is a broken app. Telling its author to cd
        somewhere else would send them looking in the wrong place.
        """
        with patch("django.setup", side_effect=ValueError("some app is wrong")):
            with pytest.raises(ValueError, match="some app is wrong"):
                _setup_django()
