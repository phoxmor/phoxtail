"""Tests for parsing --source locators into uv source entries."""

import subprocess
import tomllib

import pytest

from phoxtail.cli.utils import sources
from phoxtail.cli.utils.sources import (
    GIT,
    PATH,
    PYPI,
    URL,
    InvalidSource,
    add_source,
    package_name,
    parse_source,
    preflight,
    pypi_releases,
)


class TestParseSource:
    def test_no_locator_means_pypi(self):
        for spec in (None, "", "  ", "pypi", "PyPI"):
            assert parse_source(spec).is_pypi

    def test_git_url_keeps_its_ref(self):
        source = parse_source("git+ssh://git@github.com/phoxmor/phoxtail@main")
        assert source.kind == GIT
        assert source.location == "ssh://git@github.com/phoxmor/phoxtail"
        assert source.ref == "main"

    def test_host_at_sign_is_not_mistaken_for_a_ref(self):
        """`git@github.com` is the host; only an @ after the last / is a ref."""
        source = parse_source("git+ssh://git@github.com/phoxmor/phoxtail")
        assert source.ref is None
        assert source.location == "ssh://git@github.com/phoxmor/phoxtail"

    def test_bare_ssh_and_scp_remotes_are_git(self):
        """A remote copied out of `git remote -v` works without the git+ prefix."""
        assert parse_source("ssh://git@github.com/phoxmor/phoxtail.git").kind == GIT
        assert parse_source("git@github.com:phoxmor/phoxtail.git").kind == GIT

    def test_archive_url_is_a_url_source(self):
        source = parse_source("https://example.com/phoxtail-0.1.2-py3-none-any.whl")
        assert source.kind == URL

    def test_https_repository_without_the_git_prefix_is_rejected(self):
        """It resolves as neither an archive nor a repository, so say so."""
        with pytest.raises(InvalidSource):
            parse_source("https://github.com/phoxmor/phoxtail")

    def test_existing_directory_becomes_an_absolute_path(self, tmp_path):
        """The generated pyproject.toml is read from the new project, not from here."""
        source = parse_source(str(tmp_path))
        assert source.kind == PATH
        assert source.location == str(tmp_path.resolve())

    def test_missing_path_is_rejected(self):
        with pytest.raises(InvalidSource):
            parse_source("../no-such-checkout")


class TestEntryValue:
    def test_pypi_writes_nothing(self):
        assert parse_source(None).entry_value() is None

    def test_any_git_ref_is_written_as_rev(self):
        """Branch, tag and commit all land under `rev` — uv's own normalisation."""
        entry = parse_source("git+https://github.com/phoxmor/phoxtail@v1.2.0").entry_value()
        assert entry == '{ git = "https://github.com/phoxmor/phoxtail", rev = "v1.2.0" }'

    def test_directory_is_editable_and_archive_is_not(self, tmp_path):
        wheel = tmp_path / "phoxtail-0.1.2-py3-none-any.whl"
        wheel.write_bytes(b"")
        assert "editable = true" in parse_source(str(tmp_path)).entry_value()
        assert "editable = true" not in parse_source(str(wheel)).entry_value()


class TestPackageName:
    def test_derived_from_a_git_url(self):
        assert (
            package_name(parse_source("git+ssh://git@github.com/example/example-package.git@main")) == "example-package"
        )

    def test_not_derived_from_a_path(self, tmp_path):
        """A checkout directory may be named anything; the name must be given."""
        assert package_name(parse_source(str(tmp_path))) is None

    def test_not_derived_from_pypi(self):
        assert package_name(parse_source(None)) is None


class TestAddSourceForNonGitKinds:
    HATCHED = '[project]\nname = "demo"\ndependencies = ["phoxtail[engine]~=0.1.2"]\n\n[tool.uv]\npackage = false\n'

    def test_pypi_leaves_the_file_untouched(self):
        assert add_source(self.HATCHED, "phoxtail", parse_source(None)) == self.HATCHED

    def test_path_source_is_valid_toml(self, tmp_path):
        doc = tomllib.loads(add_source(self.HATCHED, "phoxtail", parse_source(str(tmp_path))))
        assert doc["tool"]["uv"]["sources"]["phoxtail"]["path"] == str(tmp_path.resolve())
        assert doc["tool"]["uv"]["sources"]["phoxtail"]["editable"] is True

    def test_url_source_is_valid_toml(self):
        url = "https://example.com/phoxtail-0.1.2-py3-none-any.whl"
        doc = tomllib.loads(add_source(self.HATCHED, "phoxtail", parse_source(url)))
        assert doc["tool"]["uv"]["sources"]["phoxtail"]["url"] == url


def test_pypi_constant_names_the_default():
    assert parse_source(None).kind == PYPI


class _Response:
    def __init__(self, status_code: int, payload: dict | None = None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self) -> dict:
        return self._payload


class TestPypiReleases:
    """PyPI is asked over its JSON API: `uv pip index` is gone as of uv 0.11."""

    def test_releases_are_listed(self, monkeypatch):
        payload = {"releases": {"0.1.1": [], "0.1.0": []}}
        monkeypatch.setattr(sources.httpx, "get", lambda *a, **kw: _Response(200, payload))
        assert pypi_releases("phoxtail") == ["0.1.0", "0.1.1"]

    def test_unknown_project_is_an_empty_list(self, monkeypatch):
        monkeypatch.setattr(sources.httpx, "get", lambda *a, **kw: _Response(404))
        assert pypi_releases("no-such-project") == []

    def test_unreachable_index_is_not_an_empty_list(self, monkeypatch):
        """Empty means "PyPI has no such project"; None means it never answered."""

        def boom(*args, **kwargs):
            raise sources.httpx.ConnectError("offline")

        monkeypatch.setattr(sources.httpx, "get", boom)
        assert pypi_releases("phoxtail") is None


class TestPypiPreflight:
    def test_missing_package_fails(self, monkeypatch):
        monkeypatch.setattr(sources, "pypi_releases", lambda package: [])
        reachable, message = preflight(parse_source(None), "no-such-project")
        assert reachable is False
        assert "--source" in message

    def test_unreachable_index_is_unverified_rather_than_missing(self, monkeypatch):
        """None must never be read as False: uv can still resolve from its cache."""
        monkeypatch.setattr(sources, "pypi_releases", lambda package: None)
        assert preflight(parse_source(None), "example-package")[0] is None

    def test_published_package_passes(self, monkeypatch):
        monkeypatch.setattr(sources, "pypi_releases", lambda package: ["1.0", "1.1"])
        assert preflight(parse_source(None), "example-package")[0] is True


class TestGitPreflight:
    URL = "ssh://git@github.com/example/example-package.git"

    def _ls_remote(self, monkeypatch, returncode: int, stderr: str = ""):
        def fake_run(*args, **kwargs):
            return subprocess.CompletedProcess(args=args, returncode=returncode, stdout="", stderr=stderr)

        monkeypatch.setattr(sources.subprocess, "run", fake_run)

    def test_reachable_repository_passes(self, monkeypatch):
        self._ls_remote(monkeypatch, 0)
        assert preflight(parse_source(f"git+{self.URL}"), "example-package")[0] is True

    def test_denied_access_fails(self, monkeypatch):
        self._ls_remote(monkeypatch, 128, "git@github.com: Permission denied (publickey).")
        assert preflight(parse_source(f"git+{self.URL}"), "example-package")[0] is False

    def test_offline_is_unverified_rather_than_missing(self, monkeypatch):
        """No network is not the same answer as no such repository."""
        self._ls_remote(monkeypatch, 128, "fatal: Could not resolve host: github.com")
        assert preflight(parse_source(f"git+{self.URL}"), "example-package")[0] is None

    def test_timeout_is_unverified(self, monkeypatch):
        def timeout(*args, **kwargs):
            raise subprocess.TimeoutExpired(cmd="git", timeout=30)

        monkeypatch.setattr(sources.subprocess, "run", timeout)
        assert preflight(parse_source(f"git+{self.URL}"), "example-package")[0] is None
