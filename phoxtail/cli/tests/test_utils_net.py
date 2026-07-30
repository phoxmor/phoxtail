"""Tests for cli.utils.net."""

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from phoxtail.cli.utils.net import (
    PROJECT_NET_FILE,
    Member,
    Peer,
    PeerNotRunning,
    UnknownPeer,
    add_member,
    check_compose_version,
    ensure_network,
    is_wired,
    list_peers,
    members_file,
    read_members,
    remove_env_key,
    remove_env_list_value,
    remove_member,
    resolve_peer,
    set_api_url,
    slug_in_use_elsewhere,
    upsert_env_list,
)


def _run(stdout: str, returncode: int = 0):
    """A finished `docker ps` for `subprocess.run` to return."""
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr="")


def _attached(root: Path) -> Path:
    """Create a directory that looks like an attached project.

    Both files are what `_attachment_intact` looks for, so a member entry
    only survives a read while they exist.
    """
    root.mkdir(parents=True, exist_ok=True)
    (root / "phoxtail.toml").write_text('[project]\nname = "x"\n')
    (root / PROJECT_NET_FILE).write_text("services: {}\n")
    return root


class TestUpsertEnvList:
    def test_creates_file_when_missing(self, tmp_path):
        path = tmp_path / ".env"
        upsert_env_list(path, "COMPOSE_FILE", "docker-compose.net.yaml", ":")
        assert path.read_text() == "COMPOSE_FILE=docker-compose.net.yaml\n"

    def test_appends_new_key_preserving_other_lines(self, tmp_path):
        path = tmp_path / ".env"
        path.write_text("SECRET_KEY=abc\nDEBUG=1\n")
        upsert_env_list(path, "ALLOWED_HOSTS", "alphasite.localhost", ",")
        lines = path.read_text().splitlines()
        assert "SECRET_KEY=abc" in lines
        assert "DEBUG=1" in lines
        assert "ALLOWED_HOSTS=alphasite.localhost" in lines

    def test_appends_value_to_existing_key(self, tmp_path):
        path = tmp_path / ".env"
        path.write_text("ALLOWED_HOSTS=localhost\n")
        upsert_env_list(path, "ALLOWED_HOSTS", "alphasite.localhost", ",")
        assert path.read_text() == "ALLOWED_HOSTS=localhost,alphasite.localhost\n"

    def test_idempotent_when_value_already_present(self, tmp_path):
        path = tmp_path / ".env"
        path.write_text("ALLOWED_HOSTS=localhost,alphasite.localhost\n")
        upsert_env_list(path, "ALLOWED_HOSTS", "alphasite.localhost", ",")
        assert path.read_text() == "ALLOWED_HOSTS=localhost,alphasite.localhost\n"

    def test_handles_special_characters_in_value(self, tmp_path):
        path = tmp_path / ".env"
        path.write_text("CSRF_TRUSTED_ORIGINS=http://localhost\n")
        upsert_env_list(path, "CSRF_TRUSTED_ORIGINS", "http://alphasite.localhost", ",")
        assert "http://alphasite.localhost" in path.read_text()
        assert "http://localhost" in path.read_text()

    def test_preserves_unrelated_lines_and_order(self, tmp_path):
        path = tmp_path / ".env"
        path.write_text("A=1\nCOMPOSE_FILE=docker-compose.yaml\nB=2\n")
        upsert_env_list(path, "COMPOSE_FILE", "docker-compose.net.yaml", ":")
        lines = path.read_text().splitlines()
        assert lines == ["A=1", "COMPOSE_FILE=docker-compose.yaml:docker-compose.net.yaml", "B=2"]


class TestRemoveEnvListValue:
    def test_noop_when_file_missing(self, tmp_path):
        path = tmp_path / ".env"
        remove_env_list_value(path, "COMPOSE_FILE", "docker-compose.net.yaml", ":")
        assert not path.exists()

    def test_removes_value_preserving_others(self, tmp_path):
        path = tmp_path / ".env"
        path.write_text("COMPOSE_FILE=docker-compose.yaml:docker-compose.net.yaml\n")
        remove_env_list_value(path, "COMPOSE_FILE", "docker-compose.net.yaml", ":")
        assert path.read_text() == "COMPOSE_FILE=docker-compose.yaml\n"

    def test_noop_when_value_absent(self, tmp_path):
        path = tmp_path / ".env"
        path.write_text("ALLOWED_HOSTS=localhost\n")
        remove_env_list_value(path, "ALLOWED_HOSTS", "alphasite.localhost", ",")
        assert path.read_text() == "ALLOWED_HOSTS=localhost\n"

    def test_preserves_unrelated_lines(self, tmp_path):
        path = tmp_path / ".env"
        path.write_text("A=1\nALLOWED_HOSTS=localhost,alphasite.localhost\nB=2\n")
        remove_env_list_value(path, "ALLOWED_HOSTS", "alphasite.localhost", ",")
        lines = path.read_text().splitlines()
        assert lines == ["A=1", "ALLOWED_HOSTS=localhost", "B=2"]


class TestRemoveEnvKey:
    def test_noop_when_file_missing(self, tmp_path):
        path = tmp_path / ".env"
        remove_env_key(path, "COMPOSE_FILE")
        assert not path.exists()

    def test_removes_key_entirely_preserving_others(self, tmp_path):
        path = tmp_path / ".env"
        path.write_text("A=1\nCOMPOSE_FILE=docker-compose.yaml:docker-compose.net.yaml\nB=2\n")
        remove_env_key(path, "COMPOSE_FILE")
        lines = path.read_text().splitlines()
        assert lines == ["A=1", "B=2"]

    def test_noop_when_key_absent(self, tmp_path):
        path = tmp_path / ".env"
        path.write_text("A=1\nB=2\n")
        remove_env_key(path, "COMPOSE_FILE")
        assert path.read_text().splitlines() == ["A=1", "B=2"]


class TestCheckComposeVersion:
    @patch("phoxtail.cli.utils.net.subprocess.run")
    def test_meets_minimum(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout="2.29.7\n", stderr="")
        meets_min, raw = check_compose_version()
        assert meets_min is True
        assert raw == "2.29.7"

    @patch("phoxtail.cli.utils.net.subprocess.run")
    def test_below_minimum(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout="2.20.0\n", stderr="")
        meets_min, raw = check_compose_version()
        assert meets_min is False
        assert raw == "2.20.0"

    @patch("phoxtail.cli.utils.net.subprocess.run")
    def test_command_failure(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="not found")
        meets_min, raw = check_compose_version()
        assert meets_min is False
        assert raw == "unknown"


class TestSlugInUseElsewhere:
    @patch("phoxtail.cli.utils.net.subprocess.run")
    def test_returns_other_project_dir(self, mock_run, tmp_path):
        other_dir = tmp_path.parent / "other-project"
        mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout=f"{other_dir}\n", stderr="")
        result = slug_in_use_elsewhere("alphasite", tmp_path)
        assert result == other_dir.resolve()

    @patch("phoxtail.cli.utils.net.subprocess.run")
    def test_returns_none_for_same_project(self, mock_run, tmp_path):
        mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout=f"{tmp_path}\n", stderr="")
        assert slug_in_use_elsewhere("alphasite", tmp_path) is None

    @patch("phoxtail.cli.utils.net.subprocess.run")
    def test_compares_the_project_root_not_the_cwd(self, mock_run, tmp_path, monkeypatch):
        """Docker records the compose working dir — the project root. Run
        from a subdirectory, comparing against the cwd would make a
        re-attach collide with the project itself."""
        subdir = tmp_path / "apps"
        subdir.mkdir()
        monkeypatch.chdir(subdir)
        mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout=f"{tmp_path}\n", stderr="")
        assert slug_in_use_elsewhere("alphasite", tmp_path) is None

    @patch("phoxtail.cli.utils.net.subprocess.run")
    def test_returns_none_when_no_containers(self, mock_run, tmp_path):
        mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
        assert slug_in_use_elsewhere("alphasite", tmp_path) is None

    @patch("phoxtail.cli.utils.net.subprocess.run")
    def test_raises_when_docker_fails(self, mock_run, tmp_path):
        """A guard that silently passes when Docker is down isn't a guard."""
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="Cannot connect to the Docker daemon"
        )
        with pytest.raises(RuntimeError, match="Docker daemon"):
            slug_in_use_elsewhere("alphasite", tmp_path)


class TestEnsureNetwork:
    @patch("phoxtail.cli.utils.net.subprocess.run")
    def test_raises_when_create_fails(self, mock_run):
        """attach must fail here, loudly — not at the next compose up."""
        mock_run.side_effect = [
            subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr=""),  # inspect: absent
            subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="daemon not running"),
        ]
        with pytest.raises(RuntimeError, match="daemon not running"):
            ensure_network()

    @patch("phoxtail.cli.utils.net.subprocess.run")
    def test_noop_when_network_already_exists(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
        ensure_network()
        assert mock_run.call_count == 1  # inspect only, no create


class TestListPeers:
    """`docker ps` output parsing — reachability, never membership."""

    @patch("phoxtail.cli.utils.net.subprocess.run")
    def test_parses_and_sorts_peers(self, mock_run):
        mock_run.return_value = _run("zeta-site\t/home/me/zeta\trunning\nalpha-site\t/home/me/alpha\texited\n")
        peers = list_peers()
        assert [p.slug for p in peers] == ["alpha-site", "zeta-site"]
        assert peers[0].working_dir == Path("/home/me/alpha")
        assert peers[0].running is False
        assert peers[1].running is True

    @patch("phoxtail.cli.utils.net.subprocess.run")
    def test_address_is_the_dotted_hostname(self, mock_run):
        """The only form that resolves from the host as well as inside containers.

        The bare slug is a Docker-internal alias — invisible to the host,
        where the CLI runs. Using it would also key credentials differently
        from `api_url`, splitting a project's tokens across two entries.
        """
        mock_run.return_value = _run("alpha-site\t/home/me/alpha\trunning\n")
        peer = list_peers()[0]
        assert peer.hostname == "alpha-site.localhost"
        assert peer.address == "http://alpha-site.localhost"

    @patch("phoxtail.cli.utils.net.subprocess.run")
    def test_running_container_wins_over_stale_one(self, mock_run):
        """A slug can appear twice — report what is actually reachable."""
        mock_run.return_value = _run("alpha-site\t/home/me/alpha\texited\nalpha-site\t/home/me/alpha\trunning\n")
        peers = list_peers()
        assert len(peers) == 1
        assert peers[0].running is True

    @patch("phoxtail.cli.utils.net.subprocess.run")
    def test_skips_malformed_and_unlabelled_lines(self, mock_run):
        mock_run.return_value = _run("\t/home/me/x\trunning\nnot-enough-fields\n")
        assert list_peers() == []


class _FakeTraefikResponse:
    def __init__(self, routers):
        self._routers = routers

    def raise_for_status(self):
        pass

    def json(self):
        return self._routers


class TestListPeersTraefikFallback:
    """Without a docker CLI — inside a project container — membership is read
    from Traefik's router table, which is derived from the same labels."""

    @patch("phoxtail.cli.utils.net.subprocess.run", side_effect=FileNotFoundError("docker"))
    def test_falls_back_to_traefik_routers(self, mock_run):
        routers = [
            {"rule": "Host(`zeta-site.localhost`)"},
            {"rule": "Host(`alpha-site.localhost`)"},
            {"rule": "Host(`traefik.localhost`)"},  # the dashboard, not a peer
            {"rule": "Host(`mcp.zeta-site.localhost`)"},  # a project's service, not a project
            {"rule": "Host(`mcp.alpha-site.localhost`)"},
            {"rule": "PathPrefix(`/whatever`)"},  # not a slug router
        ]
        with patch("httpx.get", return_value=_FakeTraefikResponse(routers)) as mock_get:
            peers = list_peers()

        assert [p.slug for p in peers] == ["alpha-site", "zeta-site"]
        assert all(p.running for p in peers)
        assert all(p.working_dir is None for p in peers)
        # The service name resolves on the shared network; `traefik.localhost`
        # would be an unclaimed *.localhost in-container and loop back to the
        # caller. The Host header still routes to api@internal.
        assert mock_get.call_args.args == ("http://traefik/api/http/routers",)
        assert mock_get.call_args.kwargs["headers"] == {"Host": "traefik.localhost"}

    @patch("phoxtail.cli.utils.net.subprocess.run", side_effect=FileNotFoundError("docker"))
    def test_no_peers_when_traefik_is_unreachable(self, mock_run):
        """Off the net (or the net is down), nothing is reachable anyway."""
        with patch("httpx.get", side_effect=OSError("connection refused")):
            assert list_peers() == []

    @patch("phoxtail.cli.utils.net.subprocess.run")
    def test_no_fallback_when_docker_runs_but_fails(self, mock_run):
        """A docker CLI that exists and errors is a different case from none at all.

        Only `FileNotFoundError` means "no docker here, ask Traefik". A
        non-zero exit is a real failure to report as empty, not to route
        around.
        """
        mock_run.return_value = _run("", returncode=1)
        assert list_peers() == []


class TestSetApiUrl:
    """`api_url` follows attachment state, so attach/detach rewrite it in place."""

    def test_replaces_existing_value_and_preserves_everything_else(self, tmp_path):
        path = tmp_path / "phoxtail.toml"
        path.write_text(
            "# hand-written comment\n"
            "[project]\n"
            'name = "alphasite"\n'
            "apps = []\n"
            "\n"
            "[studio]\n"
            'api_url = "http://localhost"\n'
        )
        set_api_url(path, "http://alphasite.localhost")
        content = path.read_text()

        assert 'api_url = "http://alphasite.localhost"' in content
        assert "http://localhost" not in content
        # A TOML round-trip would have dropped these; a line edit must not.
        assert "# hand-written comment" in content
        assert 'name = "alphasite"' in content
        assert "apps = []" in content

    def test_is_reversible(self, tmp_path):
        """detach must restore exactly what attach found, so the pair is a no-op."""
        path = tmp_path / "phoxtail.toml"
        original = '[project]\nname = "x"\n\n[studio]\napi_url = "http://localhost"\n'
        path.write_text(original)

        set_api_url(path, "http://x.localhost")
        set_api_url(path, "http://localhost")

        assert path.read_text() == original

    def test_adds_key_under_existing_studio_section(self, tmp_path):
        path = tmp_path / "phoxtail.toml"
        path.write_text('[project]\nname = "x"\n\n[studio]\n')
        set_api_url(path, "http://x.localhost")
        lines = path.read_text().splitlines()
        assert lines.index('api_url = "http://x.localhost"') == lines.index("[studio]") + 1

    def test_adds_studio_section_when_absent(self, tmp_path):
        path = tmp_path / "phoxtail.toml"
        path.write_text('[project]\nname = "x"\n')
        set_api_url(path, "http://x.localhost")
        content = path.read_text()
        assert "[studio]" in content
        assert 'api_url = "http://x.localhost"' in content
        assert 'name = "x"' in content

    def test_preserves_indentation(self, tmp_path):
        path = tmp_path / "phoxtail.toml"
        path.write_text('[studio]\n    api_url = "http://localhost"\n')
        set_api_url(path, "http://x.localhost")
        assert '    api_url = "http://x.localhost"' in path.read_text()

    def test_only_touches_api_url_inside_the_studio_section(self, tmp_path):
        """An identically named key in another section belongs to whoever
        put it there — the section scan must skip past it."""
        path = tmp_path / "phoxtail.toml"
        path.write_text('[deploy]\napi_url = "https://prod.example.com"\n\n[studio]\napi_url = "http://localhost"\n')
        set_api_url(path, "http://x.localhost")
        content = path.read_text()
        assert 'api_url = "https://prod.example.com"' in content
        assert 'api_url = "http://x.localhost"' in content
        assert content.count("api_url") == 2

    def test_result_is_readable_by_the_config_loader(self, tmp_path):
        """The written file must survive a real TOML parse, not just look right."""
        import tomllib

        path = tmp_path / "phoxtail.toml"
        path.write_text('[project]\nname = "x"\n')
        set_api_url(path, "http://x.localhost")
        with open(path, "rb") as fh:
            parsed = tomllib.load(fh)
        assert parsed["studio"]["api_url"] == "http://x.localhost"
        assert parsed["project"]["name"] == "x"


class TestResolvePeer:
    """The guard that must run before any peer is addressed."""

    def _peers(self, *slugs):
        return [Peer(s, Path(f"/home/me/{s}"), True) for s in slugs]

    def test_returns_the_peer_with_dotted_addresses(self):
        with patch("phoxtail.cli.utils.net.list_peers", return_value=self._peers("invoices-site")):
            peer = resolve_peer("invoices-site")
        assert peer.address == "http://invoices-site.localhost"
        assert peer.mcp_url == "http://mcp.invoices-site.localhost/mcp"

    def test_rejects_unknown_slug_and_names_the_valid_ones(self):
        """Docker resolves an unclaimed *.localhost to loopback rather than failing.

        Without this guard a misspelled peer reaches the caller's own project
        and returns 400 DisallowedHost — an error describing the wrong
        problem. The message lists real peers so an LLM can self-correct.
        """
        with patch(
            "phoxtail.cli.utils.net.list_peers",
            return_value=self._peers("invoices-site", "registry-site"),
        ):
            with pytest.raises(UnknownPeer) as exc:
                resolve_peer("invoice-site")  # one character off

        message = str(exc.value)
        assert "invoice-site" in message
        assert "invoices-site" in message
        assert "registry-site" in message

    def test_rejects_when_nothing_is_attached(self):
        with patch("phoxtail.cli.utils.net.list_peers", return_value=[]):
            with pytest.raises(UnknownPeer, match="none"):
                resolve_peer("invoices-site")

    def test_rejects_empty_and_whitespace(self):
        with patch("phoxtail.cli.utils.net.list_peers", return_value=self._peers("invoices-site")):
            for bad in ("", "   ", None):
                with pytest.raises(UnknownPeer):
                    resolve_peer(bad)

    def test_tolerates_surrounding_whitespace(self):
        with patch("phoxtail.cli.utils.net.list_peers", return_value=self._peers("invoices-site")):
            assert resolve_peer("  invoices-site  ").slug == "invoices-site"


class TestIsWired:
    """The fragment on disk is not enough — Compose only reads it if .env says so."""

    def test_true_when_compose_file_lists_the_fragment(self, tmp_path):
        (tmp_path / ".env").write_text(f"COMPOSE_FILE=docker-compose.yaml:{PROJECT_NET_FILE}\n")
        assert is_wired(tmp_path) is True

    def test_false_when_compose_file_omits_the_fragment(self, tmp_path):
        """The state that makes a project grab port 80 and fight Traefik for it."""
        (tmp_path / ".env").write_text("COMPOSE_FILE=docker-compose.yaml\n")
        assert is_wired(tmp_path) is False

    def test_false_when_no_compose_file_key(self, tmp_path):
        (tmp_path / ".env").write_text("SECRET_KEY=abc\n")
        assert is_wired(tmp_path) is False

    def test_false_when_env_missing(self, tmp_path):
        assert is_wired(tmp_path) is False


class TestMembers:
    """The members file: membership, as opposed to Docker's reachability."""

    def test_add_then_read_roundtrip(self, tmp_path):
        root = _attached(tmp_path / "alpha")
        add_member(root, "alpha-site")
        assert read_members() == [Member(root.resolve(), "alpha-site")]

    def test_reads_sorted_by_slug(self, tmp_path):
        add_member(_attached(tmp_path / "z"), "zeta-site")
        add_member(_attached(tmp_path / "a"), "alpha-site")
        assert [m.slug for m in read_members()] == ["alpha-site", "zeta-site"]

    def test_keyed_by_root_so_a_renamed_slug_replaces_the_entry(self, tmp_path):
        """The directory is the identity; the slug changes whenever someone
        edits `[project] name`. Keyed by slug, a rename would leave the old
        name behind and `net up` would start the project twice."""
        root = _attached(tmp_path / "alpha")
        add_member(root, "old-name")
        add_member(root, "new-name")
        assert read_members() == [Member(root.resolve(), "new-name")]

    def test_remove_drops_only_the_named_project(self, tmp_path):
        keep = _attached(tmp_path / "keep")
        drop = _attached(tmp_path / "drop")
        add_member(keep, "keep-site")
        add_member(drop, "drop-site")
        remove_member(drop)
        assert [m.slug for m in read_members()] == ["keep-site"]

    def test_remove_of_an_unknown_root_is_a_noop(self, tmp_path):
        add_member(_attached(tmp_path / "alpha"), "alpha-site")
        remove_member(tmp_path / "never-attached")
        assert [m.slug for m in read_members()] == ["alpha-site"]

    def test_prunes_a_project_whose_directory_is_gone(self, tmp_path):
        """Deleted or moved projects clear themselves — no GC command."""
        root = _attached(tmp_path / "alpha")
        add_member(root, "alpha-site")
        for f in root.iterdir():
            f.unlink()
        root.rmdir()
        assert read_members() == []

    def test_prunes_a_project_detached_behind_our_back(self, tmp_path):
        """Someone deleting the fragment by hand is a detach as far as the
        members file is concerned; the entry must not outlive it."""
        root = _attached(tmp_path / "alpha")
        add_member(root, "alpha-site")
        (root / PROJECT_NET_FILE).unlink()
        assert read_members() == []

    def test_pruned_entries_do_not_survive_the_next_write(self, tmp_path):
        stale = _attached(tmp_path / "stale")
        add_member(stale, "stale-site")
        (stale / PROJECT_NET_FILE).unlink()
        add_member(_attached(tmp_path / "fresh"), "fresh-site")
        assert "stale-site" not in members_file().read_text()

    def test_corrupt_file_reads_as_empty(self, tmp_path):
        """Every caller is a CLI command that must still run."""
        members_file().write_text("{ this is not json")
        assert read_members() == []

    def test_file_without_the_projects_key_reads_as_empty(self, tmp_path):
        members_file().write_text('{"something-else": []}')
        assert read_members() == []

    def test_skips_entries_missing_a_field(self, tmp_path):
        root = _attached(tmp_path / "alpha")
        members_file().write_text(json.dumps({"projects": [{"root": str(root)}, {"slug": "no-root"}]}))
        assert read_members() == []

    def test_write_leaves_no_temp_file_behind(self, tmp_path):
        """Written temp-then-rename so a crash can't truncate it; the temp
        file must not linger and be mistaken for state."""
        add_member(_attached(tmp_path / "alpha"), "alpha-site")
        assert [p.name for p in members_file().parent.iterdir()] == ["members.json"]

    def test_member_address_is_the_dotted_hostname(self):
        member = Member(Path("/home/me/alpha"), "alpha-site")
        assert member.hostname == "alpha-site.localhost"
        assert member.address == "http://alpha-site.localhost"


class TestMembersMigration:
    """With no members file, membership is recovered from container labels.

    Without this, projects attached before the file existed would vanish from
    `peers` and `net up` would find nothing to start.
    """

    @patch("phoxtail.cli.utils.net.subprocess.run")
    def test_recovers_attached_projects_from_labels(self, mock_run, tmp_path):
        root = _attached(tmp_path / "alpha")
        members_file().unlink()
        mock_run.return_value = _run(f"alpha-site\t{root}\trunning\n")
        assert read_members() == [Member(root.resolve(), "alpha-site")]

    @patch("phoxtail.cli.utils.net.subprocess.run")
    def test_excludes_a_detached_project_with_a_stale_container(self, mock_run, tmp_path):
        """The label outlives `detach` — it is stamped at container creation.
        Recovering from it blindly would re-attach a project the user
        deliberately detached."""
        root = _attached(tmp_path / "alpha")
        (root / PROJECT_NET_FILE).unlink()
        members_file().unlink()
        mock_run.return_value = _run(f"alpha-site\t{root}\texited\n")
        assert read_members() == []

    @patch("phoxtail.cli.utils.net.subprocess.run")
    def test_recovers_nothing_when_the_working_dir_is_unknown(self, mock_run, tmp_path):
        """In-container, `list_peers` falls back to Traefik and knows no
        paths. Correct: membership is host-side state anyway."""
        members_file().unlink()
        mock_run.return_value = _run("alpha-site\t\trunning\n")
        assert read_members() == []

    @patch("phoxtail.cli.utils.net.subprocess.run")
    def test_recovered_paths_are_resolved_like_add_member(self, mock_run, tmp_path):
        """Unresolved, a symlinked root would not match the entry
        `add_member` later writes, and the project would appear twice."""
        real = _attached(tmp_path / "real")
        link = tmp_path / "link"
        link.symlink_to(real)
        members_file().unlink()
        mock_run.return_value = _run(f"alpha-site\t{link}\trunning\n")
        assert read_members() == [Member(real.resolve(), "alpha-site")]


class TestSlugCollisionViaMembers:
    """Docker alone cannot see an attached project that has no container.

    `docker compose down` deletes the container carrying the slug label, so
    without the members file a second project could take the same slug
    unwarned — and `net up` would then start both, each claiming
    Host(`<slug>.localhost`) for Traefik to choose between arbitrarily.
    """

    @patch("phoxtail.cli.utils.net.subprocess.run")
    def test_detects_a_collision_with_no_container_anywhere(self, mock_run, tmp_path):
        owner = _attached(tmp_path / "owner")
        add_member(owner, "shared-slug")
        mock_run.return_value = _run("")  # docker sees nothing
        assert slug_in_use_elsewhere("shared-slug", tmp_path / "newcomer") == owner.resolve()

    @patch("phoxtail.cli.utils.net.subprocess.run")
    def test_does_not_collide_with_itself_on_reattach(self, mock_run, tmp_path):
        owner = _attached(tmp_path / "owner")
        add_member(owner, "shared-slug")
        mock_run.return_value = _run("")
        assert slug_in_use_elsewhere("shared-slug", owner) is None

    @patch("phoxtail.cli.utils.net.subprocess.run")
    def test_members_are_checked_before_docker(self, mock_run, tmp_path):
        """Answering from the file means the guard still works with Docker
        down, where the docker branch would raise instead."""
        owner = _attached(tmp_path / "owner")
        add_member(owner, "shared-slug")
        mock_run.return_value = _run("", returncode=1)  # docker would raise
        assert slug_in_use_elsewhere("shared-slug", tmp_path / "newcomer") == owner.resolve()
        mock_run.assert_not_called()


class TestResolvePeerRejectsStopped:
    """`docker ps -a` lists exited containers but Traefik only routes live ones.

    So a *correctly spelled* stopped peer hits the same loopback trap as a
    typo: the unclaimed `*.localhost` resolves to the caller itself, which
    answers 400 DisallowedHost — an error naming the wrong problem.
    """

    @patch("phoxtail.cli.utils.net.subprocess.run")
    def test_raises_naming_the_real_problem(self, mock_run):
        mock_run.return_value = _run("alpha-site\t/home/me/alpha\texited\n")
        with pytest.raises(PeerNotRunning) as exc:
            resolve_peer("alpha-site")
        message = str(exc.value)
        assert "not running" in message or "no running container" in message
        assert "/home/me/alpha" in message

    @patch("phoxtail.cli.utils.net.subprocess.run")
    def test_is_an_unknown_peer_so_existing_handlers_still_catch_it(self, mock_run):
        """mcp/peers.py catches UnknownPeer at both call sites; a sibling
        exception class would escape as an unhandled error."""
        mock_run.return_value = _run("alpha-site\t/home/me/alpha\texited\n")
        with pytest.raises(UnknownPeer):
            resolve_peer("alpha-site")

    @patch("phoxtail.cli.utils.net.subprocess.run")
    def test_running_peer_is_still_returned(self, mock_run):
        mock_run.return_value = _run("alpha-site\t/home/me/alpha\trunning\n")
        assert resolve_peer("alpha-site").slug == "alpha-site"
