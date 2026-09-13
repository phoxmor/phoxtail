`phoxtail.api.auth` gains `authenticated()`, a third option beside `guarded()`
and `scoped()`. It admits any caller whatever ceiling their credential carries,
which is what an endpoint that genuinely asks for no permission has always
meant and could not previously say: an endpoint declaring nothing keeps the
API-wide default, which refuses a scoped token, so silence and openness were
written identically and silence locks the door.

It is not `auth=None` — the authenticators still run, so an anonymous caller
still gets 401. It takes no codenames, because an endpoint with a codename to
name wants `guarded()` or `scoped()` instead.
