"""Tests for cli.utils.packages."""

from phoxtail.cli.utils.packages import (
    declared_requirement,
    entry_versions,
    has_git_source,
    is_declared,
    locked_entries,
    normalize,
)

PYPROJECT = """\
[project]
name = "demo"
dependencies = [
    "phoxtail[engine,dashboard]~=0.1.1",
    "wagtail>=7.4.2,<8.0",
    "psycopg[binary]",
    "redis",
    "colorama; sys_platform == 'win32'",
    "phoxtail-registry @ git+ssh://git@github.com/phoxmor/phoxtail-registry.git",
]

[project.optional-dependencies]
studio = ["playwright>=1.40"]

[dependency-groups]
dev = [
    "phoxtail[dev-tools]",
    "Django_Browser_Reload",
    { include-group = "docs" },
]
"""

LOCK = """\
version = 1

[[package]]
name = "wagtail"
version = "7.4.2"

[[package]]
name = "django-browser-reload"
version = "1.18.0"

[[package]]
name = "typing-extensions"
version = "4.12.0"

[[package]]
name = "typing-extensions"
version = "4.15.0"
"""


def _git_lock(sha: str) -> str:
    return (
        'version = 1\n\n[[package]]\nname = "phoxtail-registry"\nversion = "0.1.0"\n'
        f'source = {{ git = "ssh://git@github.com/phoxmor/phoxtail-registry.git?branch=main#{sha}" }}\n'
    )


class TestNormalize:
    def test_case_and_separators_collapse(self):
        assert normalize("Django_Browser.Reload") == "django-browser-reload"


class TestDeclaredRequirement:
    def test_version_specifier_does_not_hide_the_package(self):
        assert declared_requirement(PYPROJECT, "wagtail") == "wagtail>=7.4.2,<8.0"

    def test_extras_are_stripped_from_the_name(self):
        assert declared_requirement(PYPROJECT, "phoxtail") == "phoxtail[engine,dashboard]~=0.1.1"
        assert declared_requirement(PYPROJECT, "psycopg") == "psycopg[binary]"

    def test_bare_entry(self):
        assert declared_requirement(PYPROJECT, "redis") == "redis"

    def test_environment_marker(self):
        assert declared_requirement(PYPROJECT, "colorama") == "colorama; sys_platform == 'win32'"

    def test_direct_reference_url(self):
        assert declared_requirement(PYPROJECT, "phoxtail-registry").startswith("phoxtail-registry @ git+")

    def test_optional_dependencies_count_as_declared(self):
        assert is_declared(PYPROJECT, "playwright")

    def test_dependency_groups_count_as_declared(self):
        # Also covers normalization: declared as "Django_Browser_Reload".
        assert is_declared(PYPROJECT, "django-browser-reload")

    def test_runtime_only_sees_just_project_dependencies(self):
        """Neither dev groups nor the project's extras reach the production image."""
        assert not is_declared(PYPROJECT, "django-browser-reload", runtime_only=True)
        assert not is_declared(PYPROJECT, "playwright", runtime_only=True)
        assert is_declared(PYPROJECT, "wagtail", runtime_only=True)

    def test_include_group_table_is_not_a_requirement(self):
        assert not is_declared(PYPROJECT, "docs")

    def test_undeclared_package(self):
        assert declared_requirement(PYPROJECT, "celery") is None

    def test_substring_of_another_name_is_not_a_match(self):
        assert not is_declared(PYPROJECT, "wag")


class TestLockedEntries:
    def test_finds_a_locked_package(self):
        assert entry_versions(locked_entries(LOCK, "wagtail")) == ["7.4.2"]

    def test_normalizes_the_lookup(self):
        assert entry_versions(locked_entries(LOCK, "Django_Browser_Reload")) == ["1.18.0"]

    def test_collects_every_resolution_marker_variant(self):
        assert entry_versions(locked_entries(LOCK, "typing-extensions")) == ["4.12.0", "4.15.0"]

    def test_package_outside_the_graph(self):
        assert locked_entries(LOCK, "celery") == []


class TestHasGitSource:
    def test_registry_package_is_not_git_sourced(self):
        assert not has_git_source(locked_entries(LOCK, "wagtail"))
        assert has_git_source(locked_entries(_git_lock("aaaaaaa"), "phoxtail-registry"))
