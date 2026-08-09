"""Keep auto-created redirects from ever pointing at a never-published page.

``wagtail.contrib.redirects`` records a redirect for every page it moves so
shared links survive a reorder. It skips draft *descendants* of the moved
page but never checks the moved page itself, so moving an unpublished page
records a redirect whose target can only 404 — and once a later move puts
that page back onto the recorded path, the 404 resolves to a redirect to
itself and the browser stops on a redirect loop.

Only pages that have *never* been published are cleaned up here; see the
note in ``guarded`` for why "not live" is the wrong test.

This has to sit on the signal rather than in the callers: a page moves from
the admin explorer, the content API, and the agent's move tool, and a
guarantee that holds only in whichever caller remembers it is reopened by
the next one added.

Wrapping the handler, rather than connecting a second receiver, is forced
by app order. Django dispatches receivers in connection order and hatched
settings list the phoxtail apps before ``wagtail.contrib.redirects``, so a
receiver connected here would run *before* the record it means to delete
exists. Replacing the module attribute covers that order —
``wagtailredirects.ready()`` imports the name afterwards and connects the
wrapped function — and the disconnect/reconnect covers the reverse, so the
guard holds whatever the order is.
"""

from __future__ import annotations

import functools

from django.apps import apps


def install_draft_redirect_guard() -> None:
    """Purge auto-created redirects that target a not-live moved page.

    Idempotent: safe to call for however many times Django runs ``ready()``.
    """
    if not apps.is_installed("wagtail.contrib.redirects"):
        return

    from wagtail.contrib.redirects import signal_handlers
    from wagtail.signals import post_page_move

    original = signal_handlers.autocreate_redirects_on_page_move
    if getattr(original, "_phoxtail_draft_guard", False):
        return

    @functools.wraps(original)
    def guarded(instance, url_path_after, url_path_before, **kwargs):
        # Create first, exactly as wagtail would: the moved page's live
        # descendants keep their redirects, which are still valid and still
        # wanted. Only records aimed at the page itself come back out.
        original(
            instance=instance,
            url_path_after=url_path_after,
            url_path_before=url_path_before,
            **kwargs,
        )
        # "Has never been published", not "is not live" — the two differ on
        # exactly the case that makes a broad purge dangerous. A page that
        # was live once may have real links pointing at the paths it has
        # since vacated, and unpublishing it does not make those links
        # worthless: they come back the moment it is republished. Deleting
        # them would be silent, permanent link rot.
        #
        # A page that has never been published has never had a public URL,
        # so no automatic redirect to it can be worth anything — which makes
        # deleting all of them safe rather than only the ones this move
        # created, and that in turn is what lets a record left behind by an
        # earlier move get swept the next time the page moves.
        if instance.live or instance.first_published_at is not None:
            return
        from wagtail.contrib.redirects.models import Redirect

        Redirect.objects.filter(automatically_created=True, redirect_page=instance).delete()

    guarded._phoxtail_draft_guard = True
    signal_handlers.autocreate_redirects_on_page_move = guarded
    if post_page_move.disconnect(original):
        post_page_move.connect(guarded, weak=False)
