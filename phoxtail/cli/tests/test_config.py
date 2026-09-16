"""Tests for cli.utils.config."""

import pytest
import typer

from phoxtail.cli.utils.config import (
    DEFAULT_API_BASE_URL,
    _deep_merge,
    _topological_sort,
    get_api_base_url,
    get_cluster_names,
    get_clusters,
    get_project_name,
    get_public_mcp_url,
    get_public_site_url,
    load_config,
    resolve_cluster_order,
    slugify,
    validate_project_name,
)


class TestLoadConfig:
    """Test that phoxtail.toml is loaded correctly."""

    def test_loads_project_name(self):
        config = load_config()
        assert config["project"]["name"] == "phoxtail"

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


class TestApiBaseUrl:
    """Shared resolver used by the Studio CLI client, the MCP client, and
    ``phoxtail auth``. Keeping them on one helper means a change to the
    fallback rule or key normalization can't drift across call sites."""

    def test_falls_back_when_no_studio_section(self):
        # conftest SAMPLE_TOML has no [studio] — fallback applies.
        assert get_api_base_url() == DEFAULT_API_BASE_URL

    def test_reads_studio_api_url(self, tmp_path, monkeypatch):
        toml = tmp_path / "phoxtail.toml"
        toml.write_text('[project]\nname = "test"\n\n[studio]\napi_url = "http://localhost:8080"\n')
        monkeypatch.chdir(tmp_path)
        load_config.cache_clear()
        assert get_api_base_url() == "http://localhost:8080"

    def test_strips_trailing_slash(self, tmp_path, monkeypatch):
        toml = tmp_path / "phoxtail.toml"
        toml.write_text('[project]\nname = "t"\n\n[studio]\napi_url = "https://x.example.com/"\n')
        monkeypatch.chdir(tmp_path)
        load_config.cache_clear()
        assert get_api_base_url() == "https://x.example.com"

    def test_empty_api_url_falls_back(self, tmp_path, monkeypatch):
        toml = tmp_path / "phoxtail.toml"
        toml.write_text('[project]\nname = "t"\n\n[studio]\napi_url = ""\n')
        monkeypatch.chdir(tmp_path)
        load_config.cache_clear()
        assert get_api_base_url() == DEFAULT_API_BASE_URL

    def test_env_override_wins_over_config(self, tmp_path, monkeypatch):
        """PHOXTAIL_API_URL exists for processes whose network position
        differs from the host's — the mcp container reaches Django as
        `http://web` while detached (its own `localhost` is the MCP
        server, not Django), or `http://<slug>` once attached to the
        shared net. `http://web` here is just one example value the
        env override can carry — this test only checks the env var wins."""
        toml = tmp_path / "phoxtail.toml"
        toml.write_text('[project]\nname = "t"\n\n[studio]\napi_url = "http://t.localhost"\n')
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("PHOXTAIL_API_URL", "http://web/")
        load_config.cache_clear()
        assert get_api_base_url() == "http://web"

    def test_empty_env_override_is_ignored(self, monkeypatch):
        monkeypatch.setenv("PHOXTAIL_API_URL", "")
        assert get_api_base_url() == DEFAULT_API_BASE_URL


class TestPublicUrls:
    """The addresses advertised to strangers: the MCP server names the site
    as the place to obtain a credential, so what these return is what a
    client on the internet will try to reach."""

    def _project(self, tmp_path, monkeypatch, api_url="http://t.localhost"):
        toml = tmp_path / "phoxtail.toml"
        toml.write_text(f'[project]\nname = "t"\n\n[studio]\napi_url = "{api_url}"\n')
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("DOMAIN", raising=False)
        load_config.cache_clear()

    def test_locally_the_site_is_the_configured_api_url(self, tmp_path, monkeypatch):
        self._project(tmp_path, monkeypatch, "http://t.localhost/")
        assert get_public_site_url() == "http://t.localhost"
        assert get_public_mcp_url() == "http://mcp.t.localhost"

    def test_in_production_the_site_is_the_domain(self, tmp_path, monkeypatch):
        """DOMAIN is what .env already carries for nginx and certificates;
        phoxtail.toml is committed and still names the local address."""
        self._project(tmp_path, monkeypatch)
        monkeypatch.setenv("DOMAIN", "example.com")
        assert get_public_site_url() == "https://example.com"
        assert get_public_mcp_url() == "https://mcp.example.com"

    def test_the_in_network_override_never_leaks(self, tmp_path, monkeypatch):
        """Inside the mcp container PHOXTAIL_API_URL is `http://web`. That is
        where the container reaches Django, and it must never be what the
        container tells the internet — a remote client sent there would be
        sent to a host that does not exist."""
        self._project(tmp_path, monkeypatch)
        monkeypatch.setenv("PHOXTAIL_API_URL", "http://web")
        assert get_api_base_url() == "http://web"
        assert get_public_site_url() == "http://t.localhost"
        monkeypatch.setenv("DOMAIN", "example.com")
        assert get_public_site_url() == "https://example.com"

    def test_a_blank_domain_is_unset(self, tmp_path, monkeypatch):
        """A project hatched without a domain leaves `DOMAIN=` in .env."""
        self._project(tmp_path, monkeypatch)
        monkeypatch.setenv("DOMAIN", "   ")
        assert get_public_site_url() == "http://t.localhost"

    def test_a_domain_is_a_hostname_not_a_url(self, tmp_path, monkeypatch):
        """nginx and certbot already read DOMAIN as a bare hostname; a scheme
        here would advertise `https://https://…` to every remote client, so
        it fails at startup instead."""
        self._project(tmp_path, monkeypatch)
        monkeypatch.setenv("DOMAIN", "https://example.com")
        with pytest.raises(typer.BadParameter, match="hostname"):
            get_public_site_url()
        monkeypatch.setenv("DOMAIN", "example.com/")
        assert get_public_site_url() == "https://example.com"

    def test_falls_back_outside_a_project(self, monkeypatch):
        monkeypatch.delenv("DOMAIN", raising=False)
        assert get_public_site_url() == DEFAULT_API_BASE_URL
        assert get_public_mcp_url() == "http://mcp.localhost"


class TestAccessors:
    def test_get_project_name(self):
        assert get_project_name() == "phoxtail"

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
        base = {"project": {"name": "old", "version": "1"}}
        _deep_merge(base, {"project": {"name": "new"}})
        assert base["project"]["name"] == "new"
        assert base["project"]["version"] == "1"

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


class TestSlugify:
    def test_replaces_underscores_with_hyphens(self):
        assert slugify("my_project") == "my-project"

    def test_lowercases(self):
        assert slugify("MyProject") == "myproject"

    def test_mixed_case_and_underscores(self):
        assert slugify("My_Project") == "my-project"

    def test_no_underscores_passthrough(self):
        assert slugify("myproject") == "myproject"

    def test_multiple_underscores(self):
        assert slugify("my_great_project") == "my-great-project"


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
