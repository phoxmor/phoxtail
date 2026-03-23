"""Tests for cli.utils.config."""

import pytest

from phoxtail.cli.utils.config import (
    _deep_merge,
    _topological_sort,
    get_cluster_names,
    get_clusters,
    get_image_prefix,
    get_project_name,
    load_config,
    resolve_cluster_order,
    validate_project_name,
)


class TestLoadConfig:
    """Test that phoxtail.toml is loaded correctly."""

    def test_loads_project_name(self):
        config = load_config()
        assert config["project"]["name"] == "phoxtail"

    def test_loads_image_prefix(self):
        config = load_config()
        assert config["project"]["image_prefix"] == "phoxmor"

    def test_loads_clusters(self):
        config = load_config()
        clusters = config["db"]["clusters"]
        assert "cms" in clusters
        assert "booking" in clusters

    def test_cms_cluster_has_apps(self):
        clusters = get_clusters()
        assert "auth.Group" in clusters["cms"]["apps"]
        assert "wagtailcore.Page" in clusters["cms"]["apps"]

    def test_booking_cluster_has_apps(self):
        clusters = get_clusters()
        assert "booking_core" in clusters["booking"]["apps"]

    def test_booking_depends_on_cms(self):
        clusters = get_clusters()
        assert clusters["booking"]["depends_on"] == ["cms"]


class TestAccessors:
    def test_get_project_name(self):
        assert get_project_name() == "phoxtail"

    def test_get_image_prefix(self):
        assert get_image_prefix() == "phoxmor"

    def test_get_cluster_names(self):
        names = get_cluster_names()
        assert "cms" in names
        assert "booking" in names


class TestDeepMerge:
    def test_simple_override(self):
        base = {"a": 1, "b": 2}
        _deep_merge(base, {"b": 3})
        assert base == {"a": 1, "b": 3}

    def test_nested_merge(self):
        base = {"project": {"name": "old", "image_prefix": "old"}}
        _deep_merge(base, {"project": {"name": "new"}})
        assert base["project"]["name"] == "new"
        assert base["project"]["image_prefix"] == "old"

    def test_adds_new_keys(self):
        base = {"a": 1}
        _deep_merge(base, {"b": 2})
        assert base == {"a": 1, "b": 2}


class TestResolveClusterOrder:
    def test_cms_has_no_dependencies(self):
        order = resolve_cluster_order("cms")
        assert order == ["cms"]

    def test_booking_pulls_cms_first(self):
        order = resolve_cluster_order("booking")
        assert order == ["cms", "booking"]

    def test_all_returns_dependency_order(self):
        order = resolve_cluster_order("all")
        assert order.index("cms") < order.index("booking")
        assert "cms" in order
        assert "booking" in order

    def test_unknown_cluster_raises(self):
        with pytest.raises(ValueError, match="Unknown cluster"):
            resolve_cluster_order("nonexistent")


class TestValidateProjectName:
    def test_valid_name(self):
        assert validate_project_name("myproject") is None

    def test_valid_name_with_underscores(self):
        assert validate_project_name("my_project") is None

    def test_valid_name_with_digits(self):
        assert validate_project_name("project2") is None

    def test_valid_name_leading_underscore(self):
        assert validate_project_name("_private") is None

    def test_empty_string(self):
        assert validate_project_name("") is not None

    def test_starts_with_digit(self):
        assert "not a valid project name" in validate_project_name("2project")

    def test_contains_hyphen(self):
        assert "not a valid project name" in validate_project_name("my-project")

    def test_contains_space(self):
        assert "not a valid project name" in validate_project_name("my project")

    def test_contains_dot(self):
        assert "not a valid project name" in validate_project_name("my.project")

    def test_python_keyword_class(self):
        assert "Python keyword" in validate_project_name("class")

    def test_python_keyword_import(self):
        assert "Python keyword" in validate_project_name("import")

    def test_python_keyword_for(self):
        assert "Python keyword" in validate_project_name("for")

    def test_conflicts_with_stdlib_os(self):
        result = validate_project_name("os")
        assert result is not None
        assert "conflicts" in result

    def test_conflicts_with_stdlib_json(self):
        result = validate_project_name("json")
        assert result is not None
        assert "conflicts" in result

    def test_conflicts_with_stdlib_sys(self):
        result = validate_project_name("sys")
        assert result is not None
        assert "conflicts" in result

    def test_does_not_conflict_with_novel_name(self):
        assert validate_project_name("xyzzy_unique_name") is None


class TestTopologicalSort:
    def test_no_deps(self):
        clusters = {
            "a": {"apps": ["x"]},
            "b": {"apps": ["y"]},
        }
        result = _topological_sort(clusters)
        assert set(result) == {"a", "b"}

    def test_linear_deps(self):
        clusters = {
            "c": {"apps": ["z"], "depends_on": ["b"]},
            "b": {"apps": ["y"], "depends_on": ["a"]},
            "a": {"apps": ["x"]},
        }
        result = _topological_sort(clusters)
        assert result.index("a") < result.index("b")
        assert result.index("b") < result.index("c")

    def test_circular_dependency_raises(self):
        clusters = {
            "a": {"apps": ["x"], "depends_on": ["b"]},
            "b": {"apps": ["y"], "depends_on": ["a"]},
        }
        with pytest.raises(ValueError, match="Circular dependency"):
            _topological_sort(clusters)

    def test_missing_dependency_raises(self):
        clusters = {
            "a": {"apps": ["x"], "depends_on": ["missing"]},
        }
        with pytest.raises(ValueError, match="Unknown dependency"):
            _topological_sort(clusters)
