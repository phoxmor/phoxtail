"""Runtime wiring for PhoxtailAppConfig-based apps.

Called from concrete settings modules (development/production/test) once
INSTALLED_APPS, TEMPLATES, and MIDDLEWARE are assembled. Walks
INSTALLED_APPS, imports each app's `.apps` module, finds the
PhoxtailAppConfig subclass, and merges its declarations into the caller's
settings namespace.

Must run at settings load time — Django's app registry is NOT yet
populated at this point, so we use importlib directly.
"""

import importlib
import inspect

from phoxtail.core.app_config import PhoxtailAppConfig


def find_phoxtail_config(dotted_app: str) -> type[PhoxtailAppConfig] | None:
    """Import `{dotted_app}.apps` and return its PhoxtailAppConfig subclass.

    Returns None if the app has no apps.py, or no PhoxtailAppConfig
    subclass (i.e. it uses plain django.apps.AppConfig).
    """
    try:
        module = importlib.import_module(f"{dotted_app}.apps")
    except ImportError:
        return None

    for _, obj in inspect.getmembers(module, inspect.isclass):
        if (
            issubclass(obj, PhoxtailAppConfig)
            and obj is not PhoxtailAppConfig
            and obj.__module__ == module.__name__
        ):
            return obj
    return None


def _resolve_dependencies(installed_apps: list[str]) -> list[str]:
    """Expand INSTALLED_APPS to include transitive `depends_on` values.

    Preserves original order; appends missing dependencies at the first
    position they're needed. Raises ValueError on cycles.
    """
    result: list[str] = []
    seen: set[str] = set()
    chain: set[str] = set()

    def visit(app: str) -> None:
        if app in seen:
            return
        if app in chain:
            raise ValueError(f"Circular dependency in phoxtail apps: {app}")
        chain.add(app)
        config = find_phoxtail_config(app)
        if config is not None:
            for dep in config.depends_on:
                visit(dep)
        chain.discard(app)
        seen.add(app)
        result.append(app)

    for app in installed_apps:
        visit(app)
    return result


def wire_apps(settings_globals: dict) -> None:
    """Mutate a settings module's globals() to auto-wire PhoxtailAppConfigs.

    Call from settings/*.py AFTER INSTALLED_APPS, TEMPLATES, and MIDDLEWARE
    are defined, and BEFORE any code that reads those values.
    """
    installed = settings_globals["INSTALLED_APPS"]
    settings_globals["INSTALLED_APPS"] = _resolve_dependencies(installed)

    extra_context_processors: list[str] = []
    extra_middleware: list[str] = []
    default_settings: dict = {}
    celery_enabled = False

    for app in settings_globals["INSTALLED_APPS"]:
        config = find_phoxtail_config(app)
        if config is None:
            continue
        extra_context_processors.extend(config.context_processors)
        extra_middleware.extend(config.middleware)
        for key, value in dict(config.default_settings).items():
            default_settings.setdefault(key, value)
        if config.requires_celery:
            celery_enabled = True

    if extra_context_processors and settings_globals.get("TEMPLATES"):
        cps = settings_globals["TEMPLATES"][0]["OPTIONS"].setdefault(
            "context_processors", []
        )
        for cp in extra_context_processors:
            if cp not in cps:
                cps.append(cp)

    middleware = settings_globals.setdefault("MIDDLEWARE", [])
    for mw in extra_middleware:
        if mw not in middleware:
            middleware.append(mw)

    for key, value in default_settings.items():
        settings_globals.setdefault(key, value)

    settings_globals.setdefault("PHOXTAIL_CELERY_ENABLED", celery_enabled)


def collect_url_patterns():
    """Return a list of url path() entries from every PhoxtailAppConfig.

    Call from src/urls.py after the Django app registry is ready.
    """
    from django.apps import apps
    from django.urls import include, path

    patterns = []
    for config in apps.get_app_configs():
        if not isinstance(config, PhoxtailAppConfig):
            continue
        mount = config.url_mount
        if mount is None:
            continue
        if mount.namespace:
            patterns.append(
                path(mount.prefix, include((mount.module, mount.namespace)))
            )
        else:
            patterns.append(path(mount.prefix, include(mount.module)))
    return patterns
