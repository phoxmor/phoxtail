"""The scope vocabulary.

A scope names a capability a token is permitted to exercise, written as a
Django permission codename — ``"phoxtail_streams.change_blockvariant"``,
``"wagtailcore.publish_page"``. There is deliberately no vocabulary of our
own: Django already creates ``add``/``change``/``delete``/``view`` for
every model and apps declare the rest, so the list is complete, derivable
by inspection, and grows with the project at no maintenance cost.

A scope is not the same question as a permission, even though they share
a spelling. The permission asks whether the *person* may act, and some
apps answer it far more finely than a codename can — Wagtail decides
publishing per page subtree. The scope asks only whether the *credential*
they arrived with is allowed to be used for that kind of act at all. Both
must pass, and the scope is always the coarser of the two.

Which is what makes a scope safe to hold without holding the permission it
is named after. A scope is not a grant and is never checked as one: it can
only ever subtract from what the person may already do, because the
person's own check runs regardless and answers independently. So a section
editor may scope a token to ``wagtailcore.publish_page`` while holding no
global publish permission — Wagtail still decides, per page, whether that
particular publish is allowed. Minting therefore checks that a scope names
something real, not that the person minting it holds that permission;
requiring the latter would lock out exactly the users whose rights an app
models per object rather than per codename.
"""

from __future__ import annotations


def known_scopes() -> set[str]:
    """Every scope string that names a real permission.

    Read from the permission table rather than a list we maintain, so an
    app installed tomorrow contributes its scopes by migrating and nothing
    here needs to change.
    """
    from django.contrib.auth.models import Permission

    return {
        f"{app_label}.{codename}"
        for app_label, codename in Permission.objects.values_list("content_type__app_label", "codename")
    }


def unknown_scopes(scopes: list[str], known: set[str] | None = None) -> list[str]:
    """The given scopes that name no permission, in the order supplied.

    A scope that matches nothing is not a smaller grant — it is a silent
    one. It stores cleanly, survives forever, and once enforcement lands
    the token simply does less than whoever issued it believed, with
    nothing anywhere reporting why.
    """
    if not scopes:
        return []
    if known is None:
        known = known_scopes()
    return [s for s in scopes if s not in known]


def suggest(scope: str, known: set[str] | None = None, limit: int = 3) -> list[str]:
    """Close matches for an unrecognised scope, to name in the error.

    Almost every rejection here is a typo or a half-remembered app label,
    and the useful reply to both is the real spelling.

    Pass *known* when checking several scopes so the permission table is
    read once rather than once per rejection.
    """
    from difflib import get_close_matches

    if known is None:
        known = known_scopes()
    return get_close_matches(scope, known, n=limit, cutoff=0.6)
