"""Who may touch which file, asked the way Wagtail asks it.

Every other domain answers the person's half of authorization at the door,
with ``guarded()``. This one cannot. Wagtail does not grant image, document
or media permissions globally — it grants them **per collection**, as
``(group, collection, permission)`` rows, and a grant flows down to every
descendant. Verified against a running project on 2026-09-13:

    Granted add_image on one collection:
      user.has_perm('wagtailimages.add_image')       -> False
      policy.user_has_permission(user, 'add')        -> True
      collections_user_has_permission_for(…, 'add')  -> ['ZZ-Marketing', …]

``guarded()`` reads only global grants, so it would refuse someone Wagtail
genuinely allows. The endpoints here therefore split the halves: ``scoped()``
on the decorator for the credential, and these helpers inside the body, where
the collection is known. Same shape the pages endpoints use, for the same
reason — a tree, and a grant on a node covering everything under it.

**Nothing here decides anything Wagtail has not already decided.** Each
helper wraps one of the policy's own methods, and the *actions* each endpoint
asks for are copied from the Wagtail view that does the same job, rather than
chosen. That is the whole design rule for this module: media is Wagtail's
domain, and an API that answers differently from the admin about the same
file is a bug however defensible its reasoning.

Read as ``ACTIONS`` below: a chooser asks ``choose``, a library listing asks
``change``/``delete``, serving the bytes of one image asks ``change`` (that
is what ``wagtail.images.views.images.preview`` asks), and editing or
deleting asks for itself.

**The codenames are Wagtail's, not ours.** Our models are swapped in, but
Wagtail pins each policy's ``auth_model`` to its own — ``wagtailimages.Image``,
``wagtaildocs.Document``, ``wagtailmedia.Media`` — so the permissions live
under those labels and ``phoxtail_media.add_phoxtailimage`` is a row nothing
grants and nothing checks.

**And the media policy must not come from the registry.** wagtailmedia never
registers its policy there, so ``policy_registry.get_by_type()`` quietly
returns a fallback ``ModelPermissionPolicy`` naming those dead
``phoxtail_media.*`` codenames. Its own admin uses
``wagtailmedia.permissions.permission_policy``, and so must we — otherwise
the API and the admin disagree about the same file.
"""

from __future__ import annotations

from ninja.errors import HttpError

# What "may see this file" means, per library, taken from each one's own
# chooser. Images and documents have a ``choose`` permission and their
# choosers ask for it. ``wagtailmedia.Media`` has no ``choose`` row at all,
# and its chooser asks ``change``/``delete`` — so video and audio are read by
# whoever may edit them. That asymmetry is Wagtail's, not ours, and copying
# it is the point.
IMAGE_CHOOSE = ["choose"]
DOCUMENT_CHOOSE = ["choose"]
MEDIA_CHOOSE = ["change", "delete"]


def image_policy():
    from wagtail.images import get_image_model
    from wagtail.permissions import policy_registry

    return policy_registry.get_by_type(get_image_model())


def document_policy():
    from wagtail.documents import get_document_model
    from wagtail.permissions import policy_registry

    return policy_registry.get_by_type(get_document_model())


def media_policy():
    """The policy wagtailmedia's own admin uses — see the module docstring.

    Imported here rather than at module level: importing
    ``wagtailmedia.permissions`` before the app registry is ready resolves
    the wrong model and warns about it.
    """
    from wagtailmedia.permissions import permission_policy

    return permission_policy


def choosable(policy, user, actions):
    """The files *user* may see, as a queryset — Wagtail's chooser queryset.

    Both a listing and a lookup are built from this. A listing narrows to it,
    which is what Wagtail's own listings do: being shown nothing is a true
    answer to "what may I see", where a refusal would claim the act was
    forbidden. A lookup resolves *within* it, so a file the caller may not
    see answers 404 rather than 403 — also Wagtail's behaviour, and it is
    what stops a caller without a single grant from mapping the library by
    telling the two answers apart.
    """
    return policy.instances_user_has_any_permission_for(user, actions)


def require_collection(policy, user, collection) -> None:
    """403 unless *user* may add to this collection.

    Asked against the expanded set rather than the granted rows: a grant on
    a parent collection covers every collection beneath it, and only the
    policy knows how far down that reaches.
    """
    if collection not in policy.collections_user_has_permission_for(user, "add"):
        raise HttpError(403, "User cannot add files to that collection.")


def require_instance(policy, user, action, instance) -> None:
    """403 unless *user* may perform *action* on this one file.

    Finer than the collection alone. Holding only ``add`` in a collection
    still permits changing and deleting the files you uploaded yourself, so
    the owner is part of the answer and the instance has to be passed.

    A 403 here, where :func:`choosable` yields a 404 — and the split is
    Wagtail's, not an inconsistency. Its chooser resolves within the
    permitted queryset, so a file you may not see is a file that is not
    there; its edit and delete views resolve the object first and then
    refuse. Reading is the path an unprivileged caller could sweep to map
    the library, so it gives nothing away. Writing is reached by someone
    already holding a write credential, and telling them the act was
    refused is more useful than pretending the file is gone.
    """
    if not policy.user_has_permission_for_instance(user, action, instance):
        raise HttpError(403, f"User cannot {action} that file.")
