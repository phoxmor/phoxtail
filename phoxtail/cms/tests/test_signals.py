"""Auto-created redirects must never point at a never-published page.

Wagtail records a redirect for every page it moves. It skips draft
*descendants* but not the moved page itself, so moving a page that has
never been published leaves a redirect whose target can only 404 — and a
later move that puts it back on that path turns it into a redirect to
itself, i.e. a loop in the browser. ``phoxtail.cms.signals`` guards the
signal so every caller (admin explorer, content API, agent move tool) is
covered at once.

The line is "never published", not "not live". A page that was live once
may have real links pointing at the paths it has since vacated, and those
links come back on republish — deleting their redirects would be silent
link rot. Several tests below pin that distinction.
"""

from __future__ import annotations

import pytest
from wagtail.contrib.redirects.models import Redirect
from wagtail.models import Site

from phoxtail.cms.models import SitePage

# The urlconf override is load-bearing, not incidental — see tests/urls.py:
# without a reversible page route wagtail creates no redirects at all and
# every "no redirect was created" assertion below would pass vacuously.
pytestmark = [pytest.mark.django_db, pytest.mark.urls("phoxtail.cms.tests.urls")]


@pytest.fixture
def site():
    return Site.objects.get(is_default_site=True)


@pytest.fixture
def root(site):
    return site.root_page


def make_page(parent, title, slug, *, live):
    page = SitePage(title=title, slug=slug, live=live)
    parent.add_child(instance=page)
    return page


def publish(page):
    """Publish through a revision so ``first_published_at`` is set, the way
    a real publish does — the guard keys off that field."""
    page.save_revision().publish()
    page.refresh_from_db()
    return page


def test_guard_is_installed():
    """The wrapped handler, not wagtail's original, is what's connected."""
    from wagtail.contrib.redirects import signal_handlers

    assert getattr(signal_handlers.autocreate_redirects_on_page_move, "_phoxtail_draft_guard", False)


def test_moving_a_never_published_page_creates_no_redirect(root):
    destination = make_page(root, "Destination", "destination", live=True)
    draft = make_page(root, "Draft", "draft", live=False)
    assert draft.first_published_at is None

    draft.move(destination, pos="last-child")

    assert not Redirect.objects.filter(redirect_page=draft).exists()


def test_moving_a_live_page_still_creates_a_redirect(root):
    """The feature itself must survive the guard: a shared link to a live
    page keeps working after the page moves."""
    destination = make_page(root, "Destination", "destination", live=True)
    live = publish(make_page(root, "Live", "live", live=True))

    live.move(destination, pos="last-child")

    assert Redirect.objects.filter(redirect_page=live, automatically_created=True).exists()


def test_redirect_earned_while_live_survives_a_later_move_while_unpublished(root):
    """The regression this narrowing exists for.

    A page earns a redirect while live, is unpublished for a while, and is
    moved again in the meantime. The earlier redirect must survive: real
    links depend on it and republishing brings it back. An earlier version
    of this guard purged on ``not live`` and destroyed it.
    """
    destination = make_page(root, "Destination", "destination", live=True)
    page = publish(make_page(root, "Promo", "promo", live=True))

    page.move(destination, pos="last-child")
    earned = Redirect.objects.get(redirect_page=page, automatically_created=True)

    page.refresh_from_db()
    page.unpublish()
    page.refresh_from_db()
    assert not page.live and page.first_published_at is not None

    page.move(root, pos="last-child")

    assert Redirect.objects.filter(pk=earned.pk).exists()


def test_live_descendant_of_a_moved_draft_keeps_its_redirect(root):
    """Only the page itself is excluded. Its live children had real URLs
    that really moved, so their redirects are still worth having."""
    destination = make_page(root, "Destination", "destination", live=True)
    draft = make_page(root, "Draft", "draft", live=False)
    child = publish(make_page(draft, "Child", "child", live=True))

    draft.move(destination, pos="last-child")

    assert not Redirect.objects.filter(redirect_page=draft).exists()
    assert Redirect.objects.filter(redirect_page=child, automatically_created=True).exists()


def test_stale_records_for_a_never_published_page_are_swept(root, site):
    """Records leaked by an earlier move — before this guard existed — are
    safe to drop wholesale, because a never-published page never had a
    public URL for any of them to be about."""
    destination = make_page(root, "Destination", "destination", live=True)
    draft = make_page(root, "Draft", "draft", live=False)
    Redirect.objects.create(
        old_path="/stale-path",
        site=site,
        redirect_page=draft,
        automatically_created=True,
    )

    draft.move(destination, pos="last-child")

    assert not Redirect.objects.filter(redirect_page=draft).exists()


def test_a_manual_redirect_is_left_alone(root, site):
    """Only ``automatically_created`` records are the guard's business — an
    editor who deliberately pointed a path at a page keeps their record."""
    destination = make_page(root, "Destination", "destination", live=True)
    draft = make_page(root, "Draft", "draft", live=False)
    Redirect.objects.create(
        old_path="/hand-written",
        site=site,
        redirect_page=draft,
        automatically_created=False,
    )

    draft.move(destination, pos="last-child")

    assert Redirect.objects.filter(redirect_page=draft, automatically_created=False).exists()
