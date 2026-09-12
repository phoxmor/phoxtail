"""What happens when two apps reach for the same piece of the URL space.

Mounting is derived, not declared: an app's name comes from its label and its
versions come from its own ``api`` package. Nothing stops two apps arriving at
the same path — two labels can strip to the same name, and an app can pick a
name a core domain already owns. Both are silent by nature, because the second
mount simply shadows the first.

So both are refused, and both name the app that caused it.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from ninja import Router

import phoxtail.api as api_module
from phoxtail.api import _VERSION_SEGMENT, mount_discovered_routers


@pytest.fixture
def fresh_mount(monkeypatch):
    """Let the idempotence flag go, so each test performs a real mount."""
    monkeypatch.setattr(api_module, "_discovered_mounted", False)
    monkeypatch.setattr(api_module.api, "add_router", lambda *a, **k: None)


def _routers(*pairs):
    return patch("phoxtail.core.discovery.versioned_routers", return_value=iter(pairs))


class TestRefusingACollision:
    def test_a_reserved_namespace_cannot_be_taken(self, fresh_mount):
        """``/api/users/`` is still mounted by hand, so it is still reserved.

        An app landing there would shadow it, and the first sign would be a
        users endpoint answering something else. The set shrinks as each
        hand-mounted surface moves into its app; this test follows it.
        """
        with _routers(("users", {"v1": Router()})):
            with pytest.raises(RuntimeError, match="reserved by a core domain"):
                mount_discovered_routers()

    def test_two_apps_cannot_share_one_name(self, fresh_mount):
        """Reachable in practice: ``phoxtail_blog`` and a project's own ``blog``
        app both strip to ``blog``, and Django permits both labels."""
        with _routers(("blog", {"v1": Router()}), ("blog", {"v1": Router()})):
            with pytest.raises(RuntimeError, match="Two apps both try to mount"):
                mount_discovered_routers()

    def test_a_version_that_is_not_a_segment_is_refused(self, fresh_mount):
        """The key is spliced into the path, so a stray space is a dead URL."""
        with _routers(("blog", {"v1 ": Router()})):
            with pytest.raises(RuntimeError, match="not a version segment"):
                mount_discovered_routers()


class TestMountingWhatIsOffered:
    def test_every_version_an_app_declares_is_mounted(self, monkeypatch):
        monkeypatch.setattr(api_module, "_discovered_mounted", False)
        mounted = []
        monkeypatch.setattr(api_module.api, "add_router", lambda path, *a, **k: mounted.append(path))

        with _routers(("blog", {"v1": Router(), "v2": Router()})):
            mount_discovered_routers()

        assert sorted(mounted) == ["/blog/v1/", "/blog/v2/"]

    def test_mounting_twice_is_a_no_op(self, monkeypatch):
        """``ready()`` can fire more than once; the URL space must not grow."""
        monkeypatch.setattr(api_module, "_discovered_mounted", False)
        mounted = []
        monkeypatch.setattr(api_module.api, "add_router", lambda path, *a, **k: mounted.append(path))

        with _routers(("blog", {"v1": Router()})):
            mount_discovered_routers()
        with _routers(("blog", {"v1": Router()})):
            mount_discovered_routers()

        assert mounted == ["/blog/v1/"]


class TestTheVersionSegment:
    @pytest.mark.parametrize("version", ["v1", "v2", "v28"])
    def test_a_version_segment_is_accepted(self, version):
        assert _VERSION_SEGMENT.fullmatch(version)

    @pytest.mark.parametrize("version", ["", "v1 ", " v1", "1", "latest", "v1/v2", "v1.2"])
    def test_anything_else_is_not(self, version):
        assert not _VERSION_SEGMENT.fullmatch(version)
