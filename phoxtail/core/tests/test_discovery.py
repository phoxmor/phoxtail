"""Tests for phoxtail.core.discovery.

The app registry is the one registry, so these tests stand a fake registry up
rather than reaching into the project's real one: the point is what discovery
does with a set of apps, not which apps this project happens to install.
"""

from __future__ import annotations

import importlib
import sys
from unittest.mock import patch

import pytest

from phoxtail.core.app_config import PhoxtailAppConfig
from phoxtail.core.discovery import (
    app_name,
    discover,
    discover_submodules,
    phoxtail_apps,
    versioned_routers,
)

PKG = "phoxtail.core.tests.discovery_testapps"
SURFACED = f"{PKG}.app_surfaced"
BARE = f"{PKG}.app_bare"


class _FakeConfig:
    """Stands in for an AppConfig without needing one in INSTALLED_APPS."""

    def __init__(self, name, label, **attrs):
        self.name = name
        self.label = label
        for key, value in attrs.items():
            setattr(self, key, value)


def _registry(*configs):
    """Patch the app registry so discovery sees exactly *configs*."""
    return patch("django.apps.apps.get_app_configs", return_value=list(configs))


def _phoxtail_config(name, label, **attrs):
    """A config that passes discovery's isinstance check."""
    config = _FakeConfig(name, label, **attrs)
    config.__class__ = type("Config", (_FakeConfig, PhoxtailAppConfig), {})
    return config


def _forget(prefix: str) -> None:
    for dotted in [m for m in sys.modules if m.startswith(prefix)]:
        del sys.modules[dotted]


@pytest.fixture(autouse=True)
def _forget_test_surfaces():
    """Drop the fixture modules so every test observes a real import.

    Both sides of the yield: a module already cached by an earlier test would
    not be imported again, and ``_plumbing`` — which raises on import — would
    stop being able to fail. A test that cannot fail is not a test.
    """
    _forget(PKG)
    yield
    _forget(PKG)


class TestWhichAppsAreVisible:
    def test_only_phoxtail_app_configs_are_offered(self):
        """A Wagtail or contrib app is not ours, however it is named.

        Nine installed apps ship a module called ``api``. Subclassing is what
        separates them from us, and it is the whole gate.
        """
        mine = _phoxtail_config(SURFACED, "phoxtail_surfaced")
        theirs = _FakeConfig("wagtail.images", "wagtailimages")

        with _registry(mine, theirs):
            assert [name for name, _ in phoxtail_apps()] == ["surfaced"]

    def test_the_name_is_the_label_without_the_prefix(self):
        assert app_name(_FakeConfig("x", "phoxtail_dashboard")) == "dashboard"

    def test_a_label_without_the_prefix_is_used_verbatim(self):
        assert app_name(_FakeConfig("x", "phoxtail_booking_events")) == "booking_events"
        assert app_name(_FakeConfig("x", "blog")) == "blog"


class TestFindingASurface:
    def test_an_app_without_the_surface_is_skipped(self):
        """Shipping no API or no tools is ordinary, not an error."""
        with _registry(_phoxtail_config(BARE, "phoxtail_bare")):
            assert list(discover("api")) == []

    def test_an_app_with_the_surface_is_imported(self):
        with _registry(_phoxtail_config(SURFACED, "phoxtail_surfaced")):
            found = list(discover("api"))

        assert [name for name, _ in found] == ["surfaced"]
        assert found[0][1].__name__ == f"{SURFACED}.api"

    def test_a_broken_surface_raises_rather_than_disappearing(self):
        """The failure this protocol exists to prevent.

        A surface that exists but cannot import is a broken app. Swallowing it
        would turn one typo into a silently missing API — the endpoint simply
        would not be there, with nothing said.

        The error names the *dependency* that is absent, not the surface, which
        is how discovery tells the two cases apart.
        """
        config = _phoxtail_config(SURFACED, "phoxtail_surfaced")

        def raise_for_the_surface(dotted, *args, **kwargs):
            if dotted == f"{SURFACED}.api":
                raise ModuleNotFoundError("No module named 'absent'", name="absent")
            return importlib.import_module(dotted, *args, **kwargs)

        with _registry(config), patch("importlib.import_module", raise_for_the_surface):
            with pytest.raises(ModuleNotFoundError) as exc:
                list(discover("api"))

        assert exc.value.name == "absent"

    def test_an_absent_surface_is_told_apart_from_a_broken_one(self):
        """The same exception type means both things; ``name`` is the tell.

        Here the error names the surface itself — it is simply not there — and
        the app is skipped. The test above raises the same exception naming a
        dependency, and that propagates. One branch, pinned from both sides.
        """
        config = _phoxtail_config(SURFACED, "phoxtail_surfaced")
        dotted = f"{SURFACED}.api"

        def raise_absent(requested, *args, **kwargs):
            if requested == dotted:
                raise ModuleNotFoundError(f"No module named {dotted!r}", name=dotted)
            return importlib.import_module(requested, *args, **kwargs)

        with _registry(config), patch("importlib.import_module", raise_absent):
            assert list(discover("api")) == []

        assert dotted not in sys.modules


class TestWalkingTheToolPackage:
    def test_every_public_module_is_imported(self):
        """Adding a file is all it takes — there is no list to maintain."""
        with _registry(_phoxtail_config(SURFACED, "phoxtail_surfaced")):
            found = {module.__name__ for _, module in discover_submodules("mcp")}

        assert f"{SURFACED}.mcp.tools" in found

    def test_nested_packages_are_walked(self):
        """Importing a subpackage without descending registers nothing."""
        with _registry(_phoxtail_config(SURFACED, "phoxtail_surfaced")):
            found = {module.__name__ for _, module in discover_submodules("mcp")}

        assert f"{SURFACED}.mcp.nested.deeper" in found

    def test_underscored_modules_are_left_alone(self):
        """``_http`` and ``_error`` are plumbing, imported by what needs them.

        The fixture raises on import, so reaching it fails this loudly.
        """
        with _registry(_phoxtail_config(SURFACED, "phoxtail_surfaced")):
            found = {module.__name__ for _, module in discover_submodules("mcp")}

        assert f"{SURFACED}.mcp._plumbing" not in found


class TestMountableRouters:
    def test_every_declared_version_is_offered(self):
        with _registry(_phoxtail_config(SURFACED, "phoxtail_surfaced")):
            found = dict(versioned_routers())

        assert sorted(found["surfaced"]) == ["v1", "v2"]

    def test_an_api_package_declaring_nothing_is_not_mounted(self):
        """An app can hold its surface back — ``versions`` is the contract."""
        config = _phoxtail_config(BARE, "phoxtail_bare")

        with _registry(config):
            assert list(versioned_routers()) == []
