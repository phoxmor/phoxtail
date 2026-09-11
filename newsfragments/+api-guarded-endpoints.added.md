`phoxtail.api.auth.guarded()` — the `auth=` for an endpoint, naming the
codename of its act once and asking both halves of authorization about it:
whether the person holds the permission, and whether their credential covers
the scope. A token can only narrow its owner, so the person-half is what
stops one granting a codename its owner never held. The two refusals no
longer share a message — a narrowed credential is the system working and its
owner can mint a wider one, while a missing permission is not theirs to fix.
