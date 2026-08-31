"""Reconcile a project's phoxtail declarations in pyproject.toml against the current template.

`phoxtail upgrade` advances the lockfile but never touches pyproject.toml, so
when the template moves a dependency between extras, every already-hatched
project keeps declaring the old shape forever and the drift is silent. This
compares a project's phoxtail-owned entries against the template's and
reports the difference; every other dependency in the file is left alone.

Version specifiers are deliberately ignored when comparing: the template's
own copy carries an unrendered `{{ phoxtail_version }}` placeholder, and a
hatched project's version constraint is expected to differ from it on every
single upgrade.
"""

import re
import tomllib
from pathlib import Path

TEMPLATE_PYPROJECT = Path(__file__).resolve().parent.parent.parent / "project_template" / "pyproject.toml"

_MAIN_ENTRY_RE = re.compile(r"^phoxtail\[(?P<extras>[^\]]*)\](?P<spec>.*)$")
_GROUP_ENTRY_RE = re.compile(r"^phoxtail\[[^\]]*\]$")


def load_template_doc() -> dict:
    return tomllib.loads(TEMPLATE_PYPROJECT.read_text())


def _main_entry(dependencies: list[str]) -> str | None:
    return next((d for d in dependencies if d.startswith("phoxtail[")), None)


def diff_main_dependency(project_doc: dict, template_doc: dict) -> tuple[str, str] | None:
    """Compare the single `phoxtail[...]` entry in [project.dependencies].

    Returns (old_entry, new_entry) if the extras differ, else None. The
    project's own version specifier is always preserved in new_entry.
    """
    project_entry = _main_entry(project_doc.get("project", {}).get("dependencies", []))
    template_entry = _main_entry(template_doc.get("project", {}).get("dependencies", []))
    if project_entry is None or template_entry is None:
        return None
    project_m = _MAIN_ENTRY_RE.match(project_entry)
    template_m = _MAIN_ENTRY_RE.match(template_entry)
    if project_m is None or template_m is None:
        return None
    project_extras = frozenset(e.strip() for e in project_m.group("extras").split(",") if e.strip())
    template_extras = frozenset(e.strip() for e in template_m.group("extras").split(",") if e.strip())
    if project_extras == template_extras:
        return None
    new_extras = ",".join(sorted(template_extras))
    new_entry = f"phoxtail[{new_extras}]{project_m.group('spec')}"
    return project_entry, new_entry


def diff_dependency_group(project_doc: dict, template_doc: dict, group: str) -> tuple[list[str], list[str]] | None:
    """Compare the standalone `phoxtail[...]` entries in one dependency group.

    Returns (entries_to_remove, entries_to_add) if the sets differ, else None.
    """
    project_entries = project_doc.get("dependency-groups", {}).get(group, [])
    template_entries = template_doc.get("dependency-groups", {}).get(group, [])
    project_phoxtail = {e for e in project_entries if _GROUP_ENTRY_RE.match(e)}
    template_phoxtail = {e for e in template_entries if _GROUP_ENTRY_RE.match(e)}
    if project_phoxtail == template_phoxtail:
        return None
    to_remove = sorted(project_phoxtail - template_phoxtail)
    to_add = sorted(template_phoxtail - project_phoxtail)
    return to_remove, to_add


def collect_diffs(project_doc: dict, template_doc: dict) -> dict[str, tuple]:
    """Return every phoxtail-declaration diff, keyed by its location in pyproject.toml."""
    diffs: dict[str, tuple] = {}
    main_diff = diff_main_dependency(project_doc, template_doc)
    if main_diff is not None:
        diffs["project.dependencies"] = main_diff
    for group in template_doc.get("dependency-groups", {}):
        group_diff = diff_dependency_group(project_doc, template_doc, group)
        if group_diff is not None and (group_diff[0] or group_diff[1]):
            diffs[f"dependency-groups.{group}"] = group_diff
    return diffs


def apply_main_dependency_diff(text: str, old_entry: str, new_entry: str) -> str:
    return text.replace(f'"{old_entry}"', f'"{new_entry}"', 1)


def apply_group_diff(text: str, group: str, to_remove: list[str], to_add: list[str]) -> str:
    # Anchored to [dependency-groups] so a same-named array in another table
    # (e.g. [project.optional-dependencies]) is never touched.
    insertion = "".join(f'    "{entry}",\n' for entry in to_add)
    table_start = re.search(r"(?m)^\[dependency-groups\]\s*$", text)
    if table_start is None:
        # Projects hatched before the dependency-groups split have no table
        # at all — exactly the projects reconciliation exists for.
        if not to_add:
            return text
        return text.rstrip() + f"\n\n[dependency-groups]\n{group} = [\n{insertion}]\n"
    head, tail = text[: table_start.end()], text[table_start.end() :]

    for entry in to_remove:
        tail = re.sub(rf'[ \t]*"{re.escape(entry)}",?[ \t]*(#[^\n]*)?\n', "", tail, count=1)
    if to_add:
        group_start = re.search(rf"(?m)^{re.escape(group)}\s*=\s*\[\n", tail)
        if group_start is not None:
            tail = tail[: group_start.end()] + insertion + tail[group_start.end() :]
        elif re.search(rf"(?m)^{re.escape(group)}\s*=", tail) is None:
            tail = f"\n{group} = [\n{insertion}]" + tail
        # else: the group exists in a form the patcher doesn't recognise —
        # leave it alone and let the caller's re-collect report the remainder.
    return head + tail


def apply_diffs(text: str, diffs: dict[str, tuple]) -> str:
    for path, diff in diffs.items():
        if path == "project.dependencies":
            old_entry, new_entry = diff
            text = apply_main_dependency_diff(text, old_entry, new_entry)
        else:
            group = path.removeprefix("dependency-groups.")
            to_remove, to_add = diff
            text = apply_group_diff(text, group, to_remove, to_add)
    return text
