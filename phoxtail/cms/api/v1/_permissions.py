"""Who may manage which collection, asked the way Wagtail asks it.

Collections are granted **per collection**, not globally. A
``GroupCollectionPermission`` row names a group, a collection and an action,
and the grant flows down to every descendant. ``user.has_perm`` never reads
those rows, so it answers False for someone Wagtail genuinely permits —
verified against a running project on 2026-09-13:

    Granted add_collection on one branch:
      user.has_perm('wagtailcore.add_collection')     -> False
      policy.user_has_permission(user, 'add')         -> True
      instances_user_has_permission_for(…, 'add')     -> ['probe-branch']

That is why these endpoints carry ``scoped()`` rather than ``guarded()``:
the credential's half is answered at the door, and the person's half here,
where the collection is known. Same shape as media and for the same reason.

**Nothing here decides anything Wagtail has not already decided.** Each
helper wraps the policy's own methods, and the *actions* each endpoint asks
for are copied from the matching view in ``wagtail/admin/views/collections.py``
rather than chosen:

===============  =======================================================
Wagtail view     What it asks
===============  =======================================================
``Index``        any of ``add``/``change``/``delete``, excluding the root
``Create``       parent must be in the ``add`` set
``Edit``         object must be in the ``change`` set, excluding the root
``Edit`` (move)  new parent in the ``add`` set, plus :func:`may_move`
``Delete``       object must be in the ``delete`` set, excluding the root
===============  =======================================================

**There is no ``view`` action.** ``wagtailcore.view_collection`` exists
because Django creates default permissions, and a grep of the installed
wagtail package finds **no non-test reference to it at all** — the same
story as ``wagtailcore.view_page``. Wagtail answers "which collections may
I see" with the add/change/delete grants, and so do we.

**The root is narrowed, not excluded.** Wagtail drops ``depth=1`` from its
management listing but keeps it in the parent chooser, and our listing is
both — it is how an agent finds the id to create under. So it narrows by
the policy and applies no depth filter: the root appears exactly when the
caller holds a grant on it, which is exactly when they could use it as a
parent. A caller with no grant on the root cannot create top-level
collections, which is Wagtail's answer too.
"""

from __future__ import annotations

from ninja.errors import HttpError

# What "may see this collection" means, taken from Wagtail's own Index view.
# There is no ``view`` action to ask for — see the module docstring.
MANAGEABLE = ["add", "change", "delete"]


def collection_policy():
    from wagtail.permissions import collection_permission_policy

    return collection_permission_policy


def manageable(user):
    """The collections *user* may act on at all, as a queryset.

    A listing narrows to it and a lookup resolves within it, so a
    collection the caller may not touch answers 404 rather than 403 — the
    same split media uses, and for the same reason: reading is the path an
    unprivileged caller would sweep to map the tree.
    """
    return collection_policy().instances_user_has_any_permission_for(user, MANAGEABLE)


def require_action(user, action: str, collection, detail: str | None = None) -> None:
    """403 unless *user* may perform *action* on this one collection.

    Asked against the expanded set rather than the granted rows: a grant on
    an ancestor covers everything beneath it, and only the policy knows how
    far down that reaches.

    *detail* overrides the message for the one case where the collection
    being asked about is not the one being acted on — adding, where the
    target is the parent the new child will hang from.
    """
    permitted = collection_policy().instances_user_has_permission_for(user, action)
    if not permitted.filter(pk=collection.pk).exists():
        raise HttpError(403, detail or f"User cannot {action} that collection.")


def may_move(user, collection) -> bool:
    """Whether *user* may move this collection to a different parent.

    Copied from ``Edit._user_may_move_collection`` in
    ``wagtail/admin/views/collections.py``. The guard is against privilege
    escalation rather than tidiness: a grant flows *down*, so moving the
    very collection that carries your own grant changes what that grant
    reaches. Wagtail's answer is to drop the parent field from the form;
    ours is to refuse the reparent.

    Uses the policy's private ``_get_user_permission_objects_for_actions``
    because Wagtail's own view does, and owning a second copy of its grant
    resolution would be the more fragile choice. ``test_collections.py``
    asserts the attribute still exists, so a rename in a Wagtail upgrade
    fails loudly here rather than silently dropping the guard.
    """
    if user.is_active and user.is_superuser:
        return True
    grants = collection_policy()._get_user_permission_objects_for_actions(user, {"add", "change", "delete"})
    return not any(grant.collection_id == collection.pk for grant in grants)


# ---------------------------------------------------------------------------
# Site settings — granted per site
# ---------------------------------------------------------------------------

# Wagtail's settings surface asks for exactly one action. ``permission_required
# = "change"`` on its EditView is the only permission it names, and a grep of
# ``wagtail/contrib/settings`` finds **no reference to a view action at all**.
# There is no read-only settings view, so reading is what changing permits —
# the same asymmetry wagtailmedia has, where a chooser asks change/delete
# because no ``choose`` row exists. Copying it is the point.
SETTINGS_ACTION = "change"


def settings_policy():
    """The policy Wagtail's own settings admin resolves for this model.

    Wagtail 8 grants settings **per site**, through ``GroupSitePermission``
    rows and ``SitePermissionPolicy``. Verified on a running project on
    2026-09-13:

        Granted change_sitesetting on one site:
          user.has_perm('phoxtail_cms.change_sitesetting')      -> False
          policy.user_has_permission_for_instance(…, 'change')  -> True
          sites_user_has_permission_for(…, 'change')            -> [that site]

    The policy still honours a *global* grant as well — it ORs the user's own
    permissions, their groups' permissions and their groups' per-site rows —
    so ``guarded()`` would have admitted the globally granted and refused
    everyone the admin had granted per site.
    """
    from wagtail.permissions import policy_registry

    from phoxtail.cms.models import SiteSetting

    return policy_registry.get_by_type(SiteSetting)


def require_settings_access(user, setting) -> None:
    """403 unless *user* may act on this site's settings.

    Takes the ``SiteSetting`` rather than the site: the policy reads the
    instance's ``site`` field itself, and passing the object we actually
    serve keeps the question about the thing being served.

    403 rather than 404, which is the opposite of what :func:`manageable`
    does for collections — and it is Wagtail's answer. Its settings view
    raises ``PermissionDenied``, and there is no narrowed listing of
    settings to resolve within: a settings record is reached by naming a
    site, and which sites exist is a question ``/sites/`` already answers
    under its own permission.
    """
    if not settings_policy().user_has_permission_for_instance(user, SETTINGS_ACTION, setting):
        raise HttpError(403, "User cannot change settings for that site.")


# ---------------------------------------------------------------------------
# Pages — granted per subtree
# ---------------------------------------------------------------------------


def page_policy():
    """Wagtail's own page policy — grants live in ``GroupPagePermission``.

    A row names a group, a page and an action, and the grant covers that
    page's whole subtree. ``has_perm`` never reads those rows. Verified on a
    running project on 2026-09-13, granted change_page on one branch:

        user.has_perm('wagtailcore.change_page')  -> False
        policy.user_has_permission(user, 'change') -> True

    **There are six actions and no more**: ``PAGE_PERMISSION_TYPES`` is add,
    bulk_delete, change, lock, publish, unlock. ``wagtailcore.view_page`` and
    ``wagtailcore.delete_page`` exist because Django creates default
    permissions, and a grep of the installed wagtail package finds *no*
    non-test reference to ``view_page`` at all. Every ``Page`` subclass
    resolves its codenames through ``base_page_model`` to those same six, so
    ``view_sitepage`` and friends are dead rows too.
    """
    from wagtail.permissions import page_permission_policy

    return page_permission_policy


def page_actions() -> set[str]:
    """The six actions Wagtail actually grants, read from Wagtail.

    Derived rather than copied, so a Wagtail release that adds a seventh —
    a read action, say — reaches this list without anyone remembering to.
    """
    from wagtail.models import PAGE_PERMISSION_TYPES

    return {codename for codename, *_ in PAGE_PERMISSION_TYPES}


def readable_pages(user):
    """The pages *user* may read, as a queryset.

    **Not** ``explorable_instances``, and the difference matters. That set
    adds the *ancestors* of every granted page, and Wagtail says why in its
    own comment: "This will allow deeply nested pages to be accessed in the
    explorer... they will be able to navigate to D without having explicit
    access to A, B or C." It exists so a tree can be walked to reach your
    subtree — it is a navigation set, not a content set.

    These endpoints serve content, and they serve the *latest draft* of it
    (``resolve_page_for_read``). So the question is not "may I see this page
    listed" but "may I see this page's unreviewed edits", and answering it
    with the explorer's set would hand a section editor the drafts of every
    page above them. Verified on a running project: granted change_page on
    one branch, ``explorable_instances`` returned the site homepage, whose
    ``can_edit()`` for that same user was False.

    So this is the permission set proper: every page under a grant, and
    nothing else.
    """
    return page_policy().instances_user_has_any_permission_for(user, page_actions())


def require_page_readable(user, page) -> None:
    """404 unless *user* may read this page.

    404 rather than 403, as media and collections do for reads: a lookup
    resolves within the permitted set, so a page outside it is a page that
    is not there, and ids cannot be swept to map a tree you cannot see.
    The write paths answer 403 instead, because they are reached by someone
    already holding a write credential and telling them the act was refused
    is more useful than pretending the page is gone.
    """
    if not readable_pages(user).filter(pk=page.pk).exists():
        raise HttpError(404, f"Page {page.pk} not found.")
