"""Tests for cli.utils.pyproject_sync."""

import tomllib

from phoxtail.cli.utils.pyproject_sync import (
    TEMPLATE_PYPROJECT,
    apply_diffs,
    collect_diffs,
    load_template_doc,
)


def _hatched_project_text() -> str:
    """A pyproject.toml as if freshly hatched: the template with a real version."""
    return TEMPLATE_PYPROJECT.read_text().replace("{{ phoxtail_version }}", "0.1.1")


DEV_TOOLS_ONLY = """[project]
name = "demo"
dependencies = [
    "phoxtail[engine,dashboard,chatbot]~=0.1.1",
    "django-environ",
]

[dependency-groups]
dev = [
    "phoxtail[dev-tools]",
    "django-browser-reload",
]
"""


class TestCollectDiffs:
    def test_up_to_date_project_has_no_diffs(self):
        template_doc = load_template_doc()
        hatched_doc = tomllib.loads(_hatched_project_text())
        assert collect_diffs(hatched_doc, template_doc) == {}

    def test_extra_dev_entry_no_longer_in_template_is_removed(self):
        project_text = _hatched_project_text().replace(
            '"phoxtail[studio]",', '"phoxtail[studio]",\n    "phoxtail[retired-extra]",'
        )
        project_doc = tomllib.loads(project_text)
        template_doc = load_template_doc()
        diffs = collect_diffs(project_doc, template_doc)
        assert diffs["dependency-groups.dev"] == (["phoxtail[retired-extra]"], [])

    def test_missing_dev_extra_is_detected(self):
        project_doc = tomllib.loads(DEV_TOOLS_ONLY)
        template_doc = load_template_doc()
        diffs = collect_diffs(project_doc, template_doc)
        assert diffs["dependency-groups.dev"] == ([], ["phoxtail[studio]"])

    def test_main_dependency_extras_diff_preserves_version_spec(self):
        project_text = DEV_TOOLS_ONLY.replace("phoxtail[engine,dashboard,chatbot]~=0.1.1", "phoxtail[engine]~=0.1.1")
        project_doc = tomllib.loads(project_text)
        template_doc = load_template_doc()
        diffs = collect_diffs(project_doc, template_doc)
        old_entry, new_entry = diffs["project.dependencies"]
        assert old_entry == "phoxtail[engine]~=0.1.1"
        assert new_entry.endswith("~=0.1.1")
        assert set(new_entry[len("phoxtail[") : new_entry.index("]")].split(",")) == {
            "engine",
            "dashboard",
            "chatbot",
        }

    def test_differing_version_spec_alone_is_not_a_diff(self):
        # The template's own copy carries an unrendered {{ phoxtail_version }}
        # placeholder; a real project's version constraint must never be
        # flagged as drift on its own.
        project_doc = tomllib.loads(DEV_TOOLS_ONLY)
        template_doc = load_template_doc()
        diffs = collect_diffs(project_doc, template_doc)
        assert "project.dependencies" not in diffs


class TestApplyDiffs:
    def test_apply_adds_missing_entry_and_stays_valid_toml(self):
        project_doc = tomllib.loads(DEV_TOOLS_ONLY)
        template_doc = load_template_doc()
        diffs = collect_diffs(project_doc, template_doc)
        new_text = apply_diffs(DEV_TOOLS_ONLY, diffs)
        new_doc = tomllib.loads(new_text)
        assert "phoxtail[studio]" in new_doc["dependency-groups"]["dev"]
        assert "django-browser-reload" in new_doc["dependency-groups"]["dev"]

    def test_applying_twice_is_a_no_op(self):
        project_doc = tomllib.loads(DEV_TOOLS_ONLY)
        template_doc = load_template_doc()
        diffs = collect_diffs(project_doc, template_doc)
        once = apply_diffs(DEV_TOOLS_ONLY, diffs)
        assert collect_diffs(tomllib.loads(once), template_doc) == {}

    def test_apply_removes_retired_entry_without_touching_others(self):
        project_text = _hatched_project_text().replace(
            '"phoxtail[studio]",', '"phoxtail[studio]",\n    "phoxtail[retired-extra]",'
        )
        template_doc = load_template_doc()
        diffs = collect_diffs(tomllib.loads(project_text), template_doc)
        new_text = apply_diffs(project_text, diffs)
        new_dev = tomllib.loads(new_text)["dependency-groups"]["dev"]
        assert "phoxtail[retired-extra]" not in new_dev
        assert "phoxtail[studio]" in new_dev
        assert "phoxtail[dev-tools]" in new_dev
        assert "django-browser-reload" in new_dev
        assert collect_diffs(tomllib.loads(new_text), template_doc) == {}

    def test_project_without_a_dependency_groups_table_gets_one(self):
        """The phoxtail[dev] era predates dependency groups entirely."""
        legacy = (
            '[project]\nname = "demo"\ndependencies = [\n    "phoxtail[dev]~=0.1.1",\n]\n\n[tool.uv]\npackage = false\n'
        )
        template_doc = load_template_doc()
        diffs = collect_diffs(tomllib.loads(legacy), template_doc)
        new_text = apply_diffs(legacy, diffs)
        new_doc = tomllib.loads(new_text)
        assert "phoxtail[studio]" in new_doc["dependency-groups"]["dev"]
        assert new_doc["tool"]["uv"]["package"] is False
        assert collect_diffs(new_doc, template_doc) == {}

    def test_missing_group_inside_an_existing_table_is_created(self):
        no_dev_group = DEV_TOOLS_ONLY.replace(
            'dev = [\n    "phoxtail[dev-tools]",\n    "django-browser-reload",\n]', 'docs = [\n    "sphinx",\n]'
        )
        template_doc = load_template_doc()
        diffs = collect_diffs(tomllib.loads(no_dev_group), template_doc)
        new_doc = tomllib.loads(apply_diffs(no_dev_group, diffs))
        assert "phoxtail[dev-tools]" in new_doc["dependency-groups"]["dev"]
        assert "sphinx" in new_doc["dependency-groups"]["docs"]

    def test_unrecognised_formatting_reports_remaining_diff_instead_of_lying(self):
        # A single-line array is valid TOML but not one the text-based
        # patcher's insertion regex recognises — apply_diffs must not pretend
        # to have applied a change it didn't make.
        single_line = DEV_TOOLS_ONLY.replace(
            'dev = [\n    "phoxtail[dev-tools]",\n    "django-browser-reload",\n]',
            'dev = ["phoxtail[dev-tools]", "django-browser-reload"]',
        )
        template_doc = load_template_doc()
        diffs = collect_diffs(tomllib.loads(single_line), template_doc)
        new_text = apply_diffs(single_line, diffs)
        assert collect_diffs(tomllib.loads(new_text), template_doc) != {}
