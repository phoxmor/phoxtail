"""Tests for how `phoxtail install` edits the dependency list."""

import tomllib

import pytest

from phoxtail.cli.install import NoInsertionPoint, _add_dependency, _add_uv_source
from phoxtail.cli.utils.pyproject_sync import TEMPLATE_PYPROJECT

PYPROJECT = """\
[project]
name = "demo"
dependencies = [
    "wagtail>=7.4.2,<8.0",
    "psycopg[binary]",
]

[dependency-groups]
dev = [
    "django-extensions",
]

[tool.uv]
package = false
"""


def _hatched() -> str:
    """The project template as if freshly hatched."""
    return (
        TEMPLATE_PYPROJECT.read_text()
        .replace("{{ phoxtail_version }}", "0.1.1")
        .replace("{{ phoxtail_project_name }}", "demo")
    )


class TestAddDependency:
    def test_pinned_package_is_not_added_twice(self):
        """A second bare entry would leave two requirements for one distribution."""
        assert _add_dependency(PYPROJECT, "wagtail") == PYPROJECT

    def test_package_declared_with_extras_is_not_added_twice(self):
        assert _add_dependency(PYPROJECT, "psycopg") == PYPROJECT

    def test_new_package_lands_in_project_dependencies(self):
        doc = tomllib.loads(_add_dependency(PYPROJECT, "celery"))
        assert "celery" in doc["project"]["dependencies"]
        assert "celery" not in doc["dependency-groups"]["dev"]

    def test_hatched_project_gets_a_runtime_dependency(self):
        """dependency-groups.dev is dropped from the production image."""
        doc = tomllib.loads(_add_dependency(_hatched(), "celery"))
        assert "celery" in doc["project"]["dependencies"]
        assert "celery" not in doc["dependency-groups"]["dev"]

    def test_dev_group_entry_does_not_block_a_runtime_install(self):
        """dependency-groups.dev never reaches the production image."""
        doc = tomllib.loads(_add_dependency(PYPROJECT, "django-extensions"))
        assert "django-extensions" in doc["project"]["dependencies"]

    def test_empty_single_line_array_is_populated(self):
        doc = tomllib.loads(_add_dependency('[project]\nname = "demo"\ndependencies = []\n', "celery"))
        assert doc["project"]["dependencies"] == ["celery"]

    def test_single_line_array_is_appended_to(self):
        doc = tomllib.loads(_add_dependency('[project]\nname = "demo"\ndependencies = ["redis"]\n', "celery"))
        assert doc["project"]["dependencies"] == ["redis", "celery"]

    def test_file_without_a_project_table_is_an_error(self):
        """Silently returning the text unchanged would report a phantom install."""
        with pytest.raises(NoInsertionPoint):
            _add_dependency("[tool.uv]\npackage = false\n", "celery")

    def test_project_table_without_a_dependencies_array_is_an_error(self):
        with pytest.raises(NoInsertionPoint):
            _add_dependency('[project]\nname = "demo"\n\n[tool.uv]\npackage = false\n', "celery")


class TestAddUvSource:
    URL = "ssh://git@github.com/phoxmor/phoxtail-blog.git"

    def test_sources_table_is_created_when_missing(self):
        """Without it, `uv lock` would look for a private package on PyPI."""
        doc = tomllib.loads(_add_uv_source(_hatched(), "phoxtail-blog", self.URL, "main"))
        assert doc["tool"]["uv"]["sources"]["phoxtail-blog"]["git"] == self.URL
        assert doc["tool"]["uv"]["package"] is False

    def test_existing_sources_table_is_appended_to(self):
        content = f'[tool.uv.sources]\nother = {{ git = "{self.URL}x", branch = "main" }}\n'
        doc = tomllib.loads(_add_uv_source(content, "phoxtail-blog", self.URL, "dev"))
        assert doc["tool"]["uv"]["sources"]["phoxtail-blog"]["branch"] == "dev"
        assert "other" in doc["tool"]["uv"]["sources"]

    def test_source_lands_in_the_sources_table_even_when_another_table_follows(self):
        content = (
            f'[tool.uv.sources]\nother = {{ git = "{self.URL}x", branch = "main" }}\n\n[tool.uv]\npackage = false\n'
        )
        doc = tomllib.loads(_add_uv_source(content, "phoxtail-blog", self.URL, "dev"))
        assert doc["tool"]["uv"]["sources"]["phoxtail-blog"]["git"] == self.URL
        assert doc["tool"]["uv"]["package"] is False

    def test_already_present_url_is_not_added_twice(self):
        once = _add_uv_source(_hatched(), "phoxtail-blog", self.URL, "main")
        assert _add_uv_source(once, "phoxtail-blog", self.URL, "main") == once

    def test_same_url_under_another_key_does_not_block_the_source(self):
        """The check is per package: a duplicate key would be the real hazard."""
        content = f'[tool.uv.sources]\nold-name = {{ git = "{self.URL}", branch = "main" }}\n'
        doc = tomllib.loads(_add_uv_source(content, "phoxtail-blog", self.URL, "main"))
        assert doc["tool"]["uv"]["sources"]["phoxtail-blog"]["git"] == self.URL
