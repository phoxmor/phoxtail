"""Load project configuration from phoxtail.toml."""

import copy
import keyword
import os
import tomllib
from functools import lru_cache
from importlib.util import find_spec
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import typer
from rich.console import Console
from rich.panel import Panel

CONFIG_FILENAME = "phoxtail.toml"
console = Console()

# Defaults used when phoxtail.toml is missing or incomplete.
# Shaped like the parsed phoxtail.toml it is merged into, so the value type
# is whatever TOML allows at that key rather than anything narrower.
DEFAULTS: dict[str, Any] = {
    "project": {
        "name": "phoxtail",
    },
    "db": {
        "clusters": {},
    },
}


def find_config_file() -> Path | None:
    """Walk up from cwd to find phoxtail.toml."""
    current = Path.cwd()
    for parent in [current, *current.parents]:
        candidate = parent / CONFIG_FILENAME
        if candidate.is_file():
            return candidate
    return None


def require_project() -> None:
    """Exit with the standard "not a Phoxtail project" panel if no phoxtail.toml is in scope.

    Shared by the main callback's project-context gate and any command
    group (e.g. `proxy attach`/`detach`) that's exempt from that gate at
    the group level but still needs the check on specific subcommands.
    """
    if find_config_file() is None:
        console.print(
            Panel(
                "No [bold]phoxtail.toml[/bold] found in this directory or any parent.\n"
                "Run this command from the root of a Phoxtail project.",
                title="[red]Not a Phoxtail project[/red]",
                border_style="red",
                expand=False,
            )
        )
        raise typer.Exit(code=1)


@lru_cache(maxsize=1)
def load_config() -> dict:
    """Load and return the project config, merged with defaults.

    Caches the result so the file is read at most once per process.
    """
    config = copy.deepcopy(DEFAULTS)
    path = find_config_file()
    if path is not None:
        with open(path, "rb") as f:
            file_config = tomllib.load(f)
        _deep_merge(config, file_config)
    return config


def _deep_merge(base: dict, override: dict) -> None:
    """Merge override into base, recursing into nested dicts."""
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value


def get_project_name() -> str:
    return load_config()["project"]["name"]


def slugify(name: str) -> str:
    """Convert a validated project name (Python identifier) to a URL/filesystem-safe slug.

    Replaces underscores with hyphens and lowercases — the only transformation
    needed because validate_project_name already guarantees ASCII identifiers.
    """
    return name.replace("_", "-").lower()


DEFAULT_API_BASE_URL = "http://localhost"


def get_api_base_url() -> str:
    """Return the project's API base URL, without trailing slash.

    The ``PHOXTAIL_API_URL`` environment variable wins over everything:
    it exists for processes whose network position differs from the
    host's — the ``mcp`` container sets it to ``http://web``, because
    inside that container ``http://localhost`` is the MCP server itself,
    not Django. Once ``net attach`` has joined the project to the shared
    net, the net fragment overrides this to ``http://<slug>`` instead:
    the shared net gives every attached project's ``web`` the same bare
    ``web`` alias, so an unqualified lookup can resolve to a sibling
    project's Django rather than this one's; the slug alias is unique.
    Otherwise reads ``[studio] api_url`` from
    ``phoxtail.toml``; falls back to :data:`DEFAULT_API_BASE_URL` when no
    project is in scope, the file cannot be loaded, or the key is absent.
    Used by the Studio CLI client, the MCP client, and ``phoxtail auth``
    so they all agree on where the API lives and which host key indexes
    stored credentials.
    """
    env_url = os.environ.get("PHOXTAIL_API_URL")
    if env_url:
        return env_url.rstrip("/")
    if find_config_file() is None:
        return DEFAULT_API_BASE_URL
    try:
        config = load_config()
    except Exception:
        return DEFAULT_API_BASE_URL
    url = (config.get("studio") or {}).get("api_url") or DEFAULT_API_BASE_URL
    return url.rstrip("/")


def get_public_site_url() -> str:
    """Return the site's address as the outside world reaches it.

    Not :func:`get_api_base_url`. That answers "where is the API from
    where *this process* stands", and inside the ``mcp`` container it is
    ``http://web`` — correct for a request the container makes, and
    meaningless to anyone else. This one is the address a stranger on the
    internet would type, which is what gets advertised to them: the MCP
    server names it as the place to obtain a credential, so an in-network
    alias here would send every remote client to a host that does not
    exist.

    In production that is ``DOMAIN``, the same value ``.env`` already
    carries for nginx and certificates; the containers receive it through
    ``env_file``. Locally ``DOMAIN`` is unset and ``[studio] api_url``
    from ``phoxtail.toml`` is the public address.
    """
    domain = (os.environ.get("DOMAIN") or "").strip().strip("/")
    if domain:
        if "://" in domain:
            raise typer.BadParameter(f"DOMAIN must be a hostname, not a URL: {domain!r}")
        return f"https://{domain}"
    if find_config_file() is None:
        return DEFAULT_API_BASE_URL
    try:
        config = load_config()
    except Exception:
        return DEFAULT_API_BASE_URL
    url = (config.get("studio") or {}).get("api_url") or DEFAULT_API_BASE_URL
    return url.rstrip("/")


def get_public_mcp_url() -> str:
    """Return the MCP server's address as the outside world reaches it.

    The MCP server is its own origin, ``mcp.`` in front of the site's host
    — ``mcp.<slug>.localhost`` locally, ``mcp.<domain>`` in production —
    so it is derived from :func:`get_public_site_url` and needs no
    configuration of its own.
    """
    # Host only: the site is routed by host, never by path, so a path on
    # the site's address would be a mistake here rather than a prefix to
    # keep. Detached from the net the site is ``http://localhost`` and this
    # names ``http://mcp.localhost``, which nothing serves — the container
    # cannot see the port compose publishes for it. Harmless: a detached
    # laptop has no public name, so no remote client can reach it anyway.
    site = urlsplit(get_public_site_url())
    return urlunsplit((site.scheme, f"mcp.{site.netloc}", "", "", ""))


def validate_project_name(name: str) -> str | None:
    """Validate a project name for use across Django, Celery, and Docker.

    Mirrors Django's own startproject validation (isidentifier + module
    conflict check) and adds a keyword check.  Returns None when the name
    is valid, or an error message string explaining why it is not.
    """
    if not name:
        return "Project name cannot be empty."

    if not name.isidentifier():
        return (
            f"'{name}' is not a valid project name. It must start with a "
            "letter or underscore and contain only letters, digits, and "
            "underscores."
        )

    if keyword.iskeyword(name):
        return f"'{name}' conflicts with a Python keyword."

    try:
        if find_spec(name) is not None:
            return f"'{name}' conflicts with an existing Python module or package and cannot be used as a project name."
    except (ModuleNotFoundError, ValueError):
        pass

    return None


def get_docker_registry() -> str | None:
    """Return the Docker registry prefix from ``[docker] registry`` in phoxtail.toml.

    Returns None if not configured — callers should prompt the user to add it.
    Example value: ``ghcr.io/myorg``
    """
    return (load_config().get("docker") or {}).get("registry") or None


def get_clusters() -> dict[str, dict]:
    """Return the raw cluster definitions from config.

    Each cluster is a dict with 'apps' (list[str]) and optional
    'depends_on' (list[str]).
    """
    return load_config()["db"]["clusters"]


def get_cluster_names() -> list[str]:
    """Return the names of all defined clusters."""
    return list(get_clusters().keys())


def resolve_cluster_order(cluster_name: str) -> list[str]:
    """Return cluster names in dependency order for the given cluster.

    For "all", returns every cluster in dependency-safe order.
    For a specific cluster, prepends its dependencies (recursively).
    Raises ValueError for unknown clusters or circular dependencies.
    """
    clusters = get_clusters()

    if cluster_name == "all":
        return _topological_sort(clusters)

    if cluster_name not in clusters:
        raise ValueError(f"Unknown cluster: '{cluster_name}'")

    # Collect this cluster and all its transitive dependencies
    ordered: list[str] = []
    visited: set[str] = set()
    _resolve_deps(cluster_name, clusters, ordered, visited, chain=set())
    return ordered


def _resolve_deps(
    name: str,
    clusters: dict,
    ordered: list[str],
    visited: set[str],
    chain: set[str],
) -> None:
    """Recursively resolve dependencies, detecting cycles."""
    if name in chain:
        cycle = f"{' -> '.join(chain)} -> {name}"
        raise ValueError(f"Circular dependency detected: {cycle}")
    if name in visited:
        return
    if name not in clusters:
        raise ValueError(f"Unknown dependency: '{name}'")

    chain.add(name)
    for dep in clusters[name].get("depends_on", []):
        _resolve_deps(dep, clusters, ordered, visited, chain)
    chain.discard(name)
    visited.add(name)
    ordered.append(name)


def _topological_sort(clusters: dict) -> list[str]:
    """Sort all clusters in dependency order."""
    ordered: list[str] = []
    visited: set[str] = set()
    for name in clusters:
        _resolve_deps(name, clusters, ordered, visited, chain=set())
    return ordered
