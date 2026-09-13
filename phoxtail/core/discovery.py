"""How a phoxtail app's surfaces are found.

One rule, and it is the rule Django already uses for models: an app becomes
discoverable by *subclassing*
:class:`~phoxtail.core.app_config.PhoxtailAppConfig`. Inheritance is the
registration. There is no list to append to, no dotted string to declare, and
no entry point to remember.

Each discoverable app may ship two surfaces, named by convention::

    <pkg>/api/     the HTTP face   — mounted at /api/<name>/v1/
    <pkg>/mcp/     the agent face  — tools registered on the MCP server

``<name>`` is the app label with ``phoxtail_`` removed, so it is spelled once,
on the app, and the URL, the tool prefix and the MCP client's API prefix all
derive from it rather than repeating it.

Django's own ``autodiscover_modules`` is deliberately *not* used. It walks
every app in ``INSTALLED_APPS``, and nine Wagtail and django.contrib apps
already ship a module called ``api`` — filtering to ``PhoxtailAppConfig`` is
what makes the plain name ``api/`` safe for us to claim.
"""

from __future__ import annotations

import importlib
import pkgutil
from collections.abc import Iterator
from types import ModuleType
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from phoxtail.core.app_config import PhoxtailAppConfig


def app_name(config: PhoxtailAppConfig) -> str:
    """The app's one name: its label without the ``phoxtail_`` prefix."""
    return config.label.removeprefix("phoxtail_")


def phoxtail_app_configs() -> Iterator[PhoxtailAppConfig]:
    """Every app that opted in by subclassing ``PhoxtailAppConfig``.

    The single definition of "this app is ours" — subclassing is the whole
    gate. Anything that needs to ask the question asks here, so the answer
    cannot differ between two callers.

    Requires a populated app registry: call from ``AppConfig.ready()`` or
    later, never at settings-load time.
    """
    from django.apps import apps

    from phoxtail.core.app_config import PhoxtailAppConfig

    for config in apps.get_app_configs():
        if isinstance(config, PhoxtailAppConfig):
            yield config


def phoxtail_apps() -> Iterator[tuple[str, PhoxtailAppConfig]]:
    """The same apps, each paired with its name.

    Separate from :func:`phoxtail_app_configs` because the name is a separate
    question: URL mounts and context processors are read off the config and
    care nothing for what the app is called.
    """
    for config in phoxtail_app_configs():
        yield app_name(config), config


def discover(submodule: str) -> Iterator[tuple[str, ModuleType]]:
    """Import ``<pkg>.<submodule>`` for every phoxtail app that ships one.

    An app that does not ship the surface is skipped: having no API or no tool
    set is ordinary, not an error. But an ImportError raised *inside* a surface
    that does exist propagates — that is a broken app, and swallowing it would
    turn one typo into a silently missing surface, which is the exact failure
    this protocol exists to prevent.
    """
    for name, config in phoxtail_apps():
        dotted = f"{config.name}.{submodule}"
        try:
            module = importlib.import_module(dotted)
        except ModuleNotFoundError as exc:
            if exc.name == dotted:
                continue  # the surface is absent
            raise  # the surface is present and broken
        yield name, module


def discover_submodules(submodule: str) -> Iterator[tuple[str, ModuleType]]:
    """Import every public module *inside* ``<pkg>/<submodule>/``.

    The MCP face registers by import side-effect — a tool exists because
    ``@mcp_server.tool()`` ran — so importing the package is not enough, since
    these packages keep an empty ``__init__``. Walking the directory is what
    makes "add a file and the tools appear" true, with no list to maintain.

    Modules named with a leading underscore are skipped: ``_http``, ``_error``
    and friends are the app's own plumbing, imported by the tool modules that
    need them, and never a surface of their own.

    Nested packages are walked too. Importing one without descending into it
    would register nothing while looking like it had worked, and a surface
    that silently goes missing is the failure this protocol exists to prevent.
    """
    for name, package in discover(submodule):
        yield from ((name, module) for module in _walk(package))


def _walk(package: ModuleType) -> Iterator[ModuleType]:
    """Every public module under *package*, depth first.

    Deliberately catches nothing. :func:`discover` has to tell an absent
    surface from a broken one, because both raise ``ModuleNotFoundError``;
    here every module was just listed off the filesystem, so it exists and
    any failure to import it is the app being broken.
    """
    for info in pkgutil.iter_modules(getattr(package, "__path__", [])):
        if info.name.startswith("_"):
            continue
        module = importlib.import_module(f"{package.__name__}.{info.name}")
        yield module
        if info.ispkg:
            yield from _walk(module)


def versioned_routers() -> Iterator[tuple[str, dict]]:
    """Yield ``(name, {version: router})`` for every app with an HTTP face.

    An app has one by shipping ``<pkg>/api/`` that declares ``versions``.
    Nothing else is consulted.
    """
    for name, module in discover("api"):
        versions = getattr(module, "versions", None)
        if versions:
            yield name, versions
