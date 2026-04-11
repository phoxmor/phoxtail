"""Load project configuration from phoxtail.toml."""

import copy
import keyword
import tomllib
from functools import lru_cache
from importlib.util import find_spec
from pathlib import Path

CONFIG_FILENAME = "phoxtail.toml"

# Defaults used when phoxtail.toml is missing or incomplete.
DEFAULTS = {
    "project": {
        "name": "phoxtail",
    },
    "db": {
        "clusters": {},
    },
}


def _find_config_file() -> Path | None:
    """Walk up from cwd to find phoxtail.toml."""
    current = Path.cwd()
    for parent in [current, *current.parents]:
        candidate = parent / CONFIG_FILENAME
        if candidate.is_file():
            return candidate
    return None


@lru_cache(maxsize=1)
def load_config() -> dict:
    """Load and return the project config, merged with defaults.

    Caches the result so the file is read at most once per process.
    """
    config = copy.deepcopy(DEFAULTS)
    path = _find_config_file()
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
            return (
                f"'{name}' conflicts with an existing Python module or "
                "package and cannot be used as a project name."
            )
    except (ModuleNotFoundError, ValueError):
        pass

    return None


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
    ordered = []
    visited = set()
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
    ordered = []
    visited = set()
    for name in clusters:
        _resolve_deps(name, clusters, ordered, visited, chain=set())
    return ordered
