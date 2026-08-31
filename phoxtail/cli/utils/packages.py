"""Look a package up in a project's dependency declarations and lockfile.

Dependency entries are PEP 508 requirement strings — `wagtail>=7.4.2,<8.0`,
`psycopg[binary]`, `phoxtail @ git+ssh://...` — so a package name is almost
never followed by the closing quote. Matching on the raw text of
pyproject.toml misses every pinned dependency; these helpers parse the TOML
and compare PEP 503 normalized names instead.

The lockfile is the broader source of truth: it lists transitive packages
too, which is what `uv lock --upgrade-package` actually operates on.
"""

import re
import tomllib

# A requirement string always opens with the distribution name; extras,
# specifiers, markers and direct-reference URLs all follow it.
_NAME_RE = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)")


def normalize(name: str) -> str:
    """Normalize a distribution name the way PEP 503 does."""
    return re.sub(r"[-_.]+", "-", name).lower()


def module_guess(name: str) -> str:
    """Best-guess importable module for a distribution name."""
    return re.sub(r"[-_.]+", "_", name).lower()


def _requirement_name(entry: str) -> str | None:
    match = _NAME_RE.match(entry)
    return normalize(match.group(1)) if match else None


def _declared_entries(doc: dict, *, runtime_only: bool) -> list[str]:
    project = doc.get("project", {})
    entries = [e for e in project.get("dependencies", []) if isinstance(e, str)]
    if not runtime_only:
        for extra in project.get("optional-dependencies", {}).values():
            entries += [e for e in extra if isinstance(e, str)]
        # Group entries may be tables ({include-group = "..."}); only strings
        # are requirements.
        for group in doc.get("dependency-groups", {}).values():
            entries += [e for e in group if isinstance(e, str)]
    return entries


def declared_requirement(pyproject_text: str, package: str, *, runtime_only: bool = False) -> str | None:
    """Return the requirement string declaring `package`, or None if it isn't declared.

    `runtime_only=True` looks only at [project].dependencies: dependency
    groups and the project's own extras never reach the production image
    (`uv sync --frozen --no-dev` installs neither), so a package declared only
    there still needs installing as a runtime dependency. Upgrades keep the
    default — any declaration constrains resolution all the same.
    """
    target = normalize(package)
    for entry in _declared_entries(tomllib.loads(pyproject_text), runtime_only=runtime_only):
        if _requirement_name(entry) == target:
            return entry
    return None


def is_declared(pyproject_text: str, package: str, *, runtime_only: bool = False) -> bool:
    """Whether `package` is declared directly in pyproject.toml."""
    return declared_requirement(pyproject_text, package, runtime_only=runtime_only) is not None


def locked_entries(lock_text: str, package: str) -> list[dict]:
    """Every `[[package]]` table matching `package` in a uv lockfile.

    A package can appear more than once under different resolution markers,
    and an empty list means it is not in the resolved graph at all.
    """
    target = normalize(package)
    return [
        entry for entry in tomllib.loads(lock_text).get("package", []) if normalize(entry.get("name", "")) == target
    ]


def entry_versions(entries: list[dict]) -> list[str]:
    """The distinct versions across `entries`, for display."""
    return sorted({entry.get("version", "") for entry in entries})


def has_git_source(entries: list[dict]) -> bool:
    """Whether any entry resolves from git rather than a registry."""
    return any("git" in entry.get("source", {}) for entry in entries)
