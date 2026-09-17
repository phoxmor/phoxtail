"""The scope vocabulary an outside client is given.

Inside the project a credential's ceiling is a list of permission codenames
(:mod:`phoxtail.tokens.scopes`). A codename is a row Django may rewrite in a
migration — rename a model and every ``view_<model>`` is silently a
different string. A token minted for a client we control can be reminted;
a scope stored by a client on someone else's servers is a promise we
cannot take back. So codenames never leave the project. An outsider asks
for a **bundle**: a stable name, one read/write pair per app, that this
module maps to codenames at the moment a credential is read.

The mapping is derived, never typed. Every endpoint and tool already names
the codename its act needs, once, in its ``auth=``; the bundle *is* what
the app's doors ask for. Add a door and its codename joins the bundle by
existing. An app whose doors ask for nothing has no bundle: a name that
expands to nothing would be a name a client could request and be granted
nothing by, with nothing reporting why.

The bundle takes the app's name — the same word in its URL prefix and its
tool names — so there is one name per app to hold, and the description a
person reads on the consent screen takes the app's verbose name.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterable, Iterator
from functools import cache
from urllib.parse import urlsplit

from oauth2_provider.oauth2_validators import OAuth2Validator
from oauth2_provider.scopes import BaseScopes

READ = "read"
WRITE = "write"

# The act half of a codename that only looks: Django's ``view_`` and
# Wagtail's ``choose_``, which admits a picker. Everything else changes
# something and is a write.
_READ_ACTS = ("view_", "choose_")


def is_read(codename: str) -> bool:
    """Whether *codename* names an act that only looks."""
    _, _, act = codename.partition(".")
    return act.startswith(_READ_ACTS)


def _endpoint_codenames(router) -> Iterator[str]:
    """Every codename an endpoint under *router* names.

    ``build_routers`` is ninja's own non-mutating flattening of a router
    and its children; each mount's template holds the operations as
    declared, with the ``auth=`` given at decoration already resolved.
    """
    for mount in router.build_routers(""):
        for view in mount.template.path_operations.values():
            for operation in view.operations:
                for check in operation.auth_callbacks:
                    yield from getattr(check, "codenames", ())


def _run(coroutine):
    """Run *coroutine* to completion from synchronous code.

    The first call may come from inside a running loop — the MCP server's
    own, when a tool asks — where ``asyncio.run`` refuses; a thread with
    a loop of its own answers there.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coroutine)
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coroutine).result()


def _app_of(module_name: str, apps: dict[str, str]) -> str | None:
    """The app name whose package *module_name* lives in, if any."""
    for package, name in apps.items():
        if module_name == package or module_name.startswith(package + "."):
            return name
    return None


def _tool_codenames(apps: dict[str, str]) -> Iterator[tuple[str, str]]:
    """``(app name, codename)`` for every tool's scope check.

    Read off the provider, not the server's filtered listing: the listing
    runs every component's checks against the current caller, and taken
    outside a transport that is nobody, so it would answer with the tools
    a stranger may see — none of the scoped ones.
    """
    from phoxtail.mcp import mcp_server, register_tools

    register_tools()
    tools = _run(mcp_server.local_provider.list_tools())
    for tool in tools:
        fn = getattr(tool, "fn", None)
        name = _app_of(getattr(fn, "__module__", ""), apps)
        if name is None:
            continue  # the server's own tools, which belong to no app
        for check in tool.auth or ():
            for codename in getattr(check, "required_scopes", ()):
                yield name, codename


@cache
def derive() -> dict[str, frozenset[str]]:
    """Bundle name to the codenames it stands for, read from the doors.

    Computed once per process: the doors are declared in code and do not
    change while it runs. The web and MCP servers each compute their own
    copy, so an app installed later reaches both documents only when both
    have restarted. Requires the app registry and both surfaces, so it is
    called from views and tools, never at import.
    """
    from phoxtail.core.discovery import phoxtail_apps, versioned_routers

    apps = {config.name: name for name, config in phoxtail_apps()}
    named: dict[str, set[str]] = {}
    for name, versions in versioned_routers():
        for router in versions.values():
            named.setdefault(name, set()).update(_endpoint_codenames(router))
    for name, codename in _tool_codenames(apps):
        named.setdefault(name, set()).add(codename)

    bundles: dict[str, frozenset[str]] = {}
    for name in sorted(named):
        codenames = named[name]
        if not codenames:
            continue
        reads = frozenset(c for c in codenames if is_read(c))
        if reads:
            bundles[f"{name}:{READ}"] = reads
        # A client that may change something may also look at it: the
        # write bundle carries the read bundle, so "write" reads as
        # "read and write" and a client holding it alone meets no wall.
        bundles[f"{name}:{WRITE}"] = frozenset(codenames)
    return bundles


def is_bundle(name: str) -> bool:
    """Whether a stored scope name is a bundle rather than a codename.

    Asked of the table, not of the spelling: a bundle is a name the table
    has, whatever shape scopes take later. (No codename can be one — a
    bundle joins its halves with a colon and a codename joins the app
    label to Django's ``[a-z_]+`` with a dot — but nothing relies on that.)
    A bundle that no longer exists reads as a codename no door names.
    """
    return name in derive()


def expand(names: Iterable[str]) -> frozenset[str]:
    """The codenames the given stored names stand for, today.

    A key carries names; a door asks codenames. A bundle expands to its
    codenames as derived now, so it can be repointed and no issued key
    changes meaning; a codename is already atomic and stands for itself.
    Applied when a key is read, never when it is minted. A bundle name
    that no longer exists expands to nothing.
    """
    table = derive()
    codenames: set[str] = set()
    for name in names:
        if is_bundle(name):
            codenames |= table.get(name, frozenset())
        else:
            codenames.add(name)
    return frozenset(codenames)


def describe(bundle: str) -> str:
    """What a person is told the bundle permits, on the consent screen."""
    from phoxtail.core.discovery import phoxtail_apps

    name, _, act = bundle.partition(":")
    subject = next((config.verbose_name for app, config in phoxtail_apps() if app == name), name)
    if act == READ:
        return f"Read {subject}"
    return f"Read and change {subject}"


class Bundles(BaseScopes):
    """The authorization server's scope backend: the bundles, and only them.

    Feeds the discovery document's ``scopes_supported``, the consent
    screen's descriptions and the validation of every request. No
    defaults: a client that asks for nothing is granted nothing, rather
    than everything.
    """

    def get_all_scopes(self):
        return {bundle: describe(bundle) for bundle in derive()}

    def get_available_scopes(self, application=None, request=None, *args, **kwargs):
        return list(derive())

    def get_default_scopes(self, application=None, request=None, *args, **kwargs):
        return []


LOOPBACK_HOSTS = ("localhost", "127.0.0.1", "::1")


class Validator(OAuth2Validator):
    """The library's validator, with two rules of phoxtail's.

    A request that asks for nothing is refused. With no default scopes
    the library validates an empty request as a subset of everything and
    lets it through to a consent screen that cannot be approved — its
    form requires a scope. The standard's other answer is to fail the
    request as ``invalid_scope``, which sends the client an error it
    understands instead of leaving a person on a form.

    A plaintext redirect goes only to loopback. A code is delivered to
    the redirect URI, and over ``http`` it is delivered in the clear —
    which is fine for a program listening on the machine the browser is
    on, and nothing else. The library's own switch is site-wide, so
    ``http`` is allowed for the loopback clients that need it and refused
    here for any other host, whatever a client registered.
    """

    def validate_scopes(self, client_id, scopes, client, request, *args, **kwargs):
        # A missing scope arrives as an empty list; a blank one as [""].
        if not any(scopes):
            return False
        return super().validate_scopes(client_id, scopes, client, request, *args, **kwargs)

    def validate_redirect_uri(self, client_id, redirect_uri, request, *args, **kwargs):
        parts = urlsplit(redirect_uri)
        if parts.scheme == "http" and parts.hostname not in LOOPBACK_HOSTS:
            return False
        return super().validate_redirect_uri(client_id, redirect_uri, request, *args, **kwargs)
