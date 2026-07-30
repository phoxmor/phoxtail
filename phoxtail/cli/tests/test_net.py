"""Tests for the `phoxtail net` command group."""

import json
import re
from pathlib import Path
from unittest.mock import patch

import yaml
from typer.testing import CliRunner

from phoxtail.cli import net
from phoxtail.cli.net import app as net_app
from phoxtail.cli.utils.config import DEFAULT_API_BASE_URL, get_api_base_url, load_config
from phoxtail.cli.utils.net import NETWORK_NAME, SLUG_LABEL, Member, Peer, read_members

runner = CliRunner()

CUSTOM_TOML = """\
[project]
name = "alphasite"
"""


def _use_custom_project_name(tmp_path: Path) -> None:
    """Overwrite the autouse project_dir fixture's phoxtail.toml with a non-default name."""
    (tmp_path / "phoxtail.toml").write_text(CUSTOM_TOML)
    load_config.cache_clear()


def _env_list(env_content: str, key: str) -> list[str]:
    """Return the comma-separated values of ``KEY=`` in an env file's text."""
    for line in env_content.splitlines():
        if line.startswith(f"{key}="):
            return [v for v in (p.strip() for p in line[len(key) + 1 :].split(",")) if v]
    return []


def _strip_reset_tags(content: str) -> str:
    """Drop Compose's `!reset` tags so PyYAML can parse the fragment.

    `!reset` is a Compose-specific tag (2.24+), unknown to PyYAML. Tests
    that assert on structure don't care about it — the tag's presence is
    asserted separately as raw text.
    """
    return re.sub(r"!reset\s+", "", content)


class TestUp:
    def test_creates_network_and_starts_stack(self, tmp_path, monkeypatch):
        monkeypatch.setattr(net, "NET_DIR", tmp_path / "net")
        monkeypatch.setattr(net, "NET_COMPOSE_FILE", tmp_path / "net" / "docker-compose.yaml")
        with (
            patch("phoxtail.cli.net.ensure_network") as mock_ensure,
            patch("phoxtail.cli.net.subprocess.call", return_value=0) as mock_call,
        ):
            result = runner.invoke(net_app, ["up"])
        assert result.exit_code == 0
        mock_ensure.assert_called_once()
        cmd = mock_call.call_args[0][0]
        assert cmd[:3] == ["docker", "compose", "-f"]
        assert cmd[-2:] == ["up", "-d"]
        assert (tmp_path / "net" / "docker-compose.yaml").exists()

    def test_stack_declares_its_compose_project_name(self, tmp_path, monkeypatch):
        """Left implicit, the project name would be the directory's ("net"),
        naming the router `net-traefik-1` after nothing recognisable."""
        monkeypatch.setattr(net, "NET_DIR", tmp_path / "net")
        monkeypatch.setattr(net, "NET_COMPOSE_FILE", tmp_path / "net" / "docker-compose.yaml")
        with (
            patch("phoxtail.cli.net.ensure_network"),
            patch("phoxtail.cli.net.subprocess.call", return_value=0),
        ):
            runner.invoke(net_app, ["up"])

        stack = yaml.safe_load((tmp_path / "net" / "docker-compose.yaml").read_text())
        assert stack["name"] == NETWORK_NAME
        assert "traefik" in stack["services"]


class TestDown:
    def test_noop_when_not_set_up(self, tmp_path, monkeypatch):
        monkeypatch.setattr(net, "NET_COMPOSE_FILE", tmp_path / "net" / "docker-compose.yaml")
        with patch("phoxtail.cli.net.subprocess.call") as mock_call:
            result = runner.invoke(net_app, ["down"])
        assert result.exit_code == 0
        mock_call.assert_not_called()

    def test_stops_stack_when_present(self, tmp_path, monkeypatch):
        compose_file = tmp_path / "net" / "docker-compose.yaml"
        compose_file.parent.mkdir(parents=True)
        compose_file.write_text("services: {}\n")
        monkeypatch.setattr(net, "NET_COMPOSE_FILE", compose_file)
        with patch("phoxtail.cli.net.subprocess.call", return_value=0) as mock_call:
            result = runner.invoke(net_app, ["down"])
        assert result.exit_code == 0
        cmd = mock_call.call_args[0][0]
        assert cmd == ["docker", "compose", "-f", str(compose_file), "down"]


class TestAttach:
    def test_refuses_with_default_project_name(self, tmp_path):
        # autouse project_dir fixture already wrote phoxtail.toml with name="phoxtail",
        # which matches the DEFAULTS fallback. Compose-version/collision checks are
        # mocked so this test can only pass because of the name guard, not by accident.
        with (
            patch("phoxtail.cli.net.check_compose_version", return_value=(True, "2.29.0")),
            patch("phoxtail.cli.net.slug_in_use_elsewhere", return_value=None),
        ):
            result = runner.invoke(net_app, ["attach"])
        assert result.exit_code == 1
        assert "project] name" in result.output

    def test_refuses_on_old_compose_version(self, tmp_path):
        _use_custom_project_name(tmp_path)
        with patch("phoxtail.cli.net.check_compose_version", return_value=(False, "2.10.0")):
            result = runner.invoke(net_app, ["attach"])
        assert result.exit_code == 1
        assert "2.10.0" in result.output

    def test_refuses_on_slug_collision(self, tmp_path):
        _use_custom_project_name(tmp_path)
        with (
            patch("phoxtail.cli.net.check_compose_version", return_value=(True, "2.29.0")),
            patch("phoxtail.cli.net.slug_in_use_elsewhere", return_value=Path("/elsewhere")),
        ):
            result = runner.invoke(net_app, ["attach"])
        assert result.exit_code == 1
        assert "/elsewhere" in result.output

    def test_writes_net_compose_and_wires_env(self, tmp_path):
        _use_custom_project_name(tmp_path)
        (tmp_path / ".env").write_text(
            "SECRET_KEY=abc\nALLOWED_HOSTS=localhost\nCSRF_TRUSTED_ORIGINS=http://localhost\n"
        )

        with (
            patch("phoxtail.cli.net.check_compose_version", return_value=(True, "2.29.0")),
            patch("phoxtail.cli.net.slug_in_use_elsewhere", return_value=None),
            patch("phoxtail.cli.net.ensure_network"),
        ):
            result = runner.invoke(net_app, ["attach"])

        assert result.exit_code == 0, result.output

        net_file = tmp_path / "docker-compose.net.yaml"
        assert net_file.exists()
        content = net_file.read_text()
        assert "alphasite.localhost" in content
        assert "ports: !reset []" in content

        env_content = (tmp_path / ".env").read_text()
        assert "SECRET_KEY=abc" in env_content
        assert "COMPOSE_FILE=docker-compose.yaml:docker-compose.net.yaml" in env_content
        # `web` rides along as a repair for projects hatched before the env
        # template shipped it — the mcp service reaches the API by that name.
        assert "ALLOWED_HOSTS=localhost,alphasite.localhost,alphasite,web" in env_content
        assert "CSRF_TRUSTED_ORIGINS=http://localhost,http://alphasite.localhost" in env_content

    def test_allows_the_bare_slug_as_a_host(self, tmp_path):
        """Peer calls arrive as `Host: <slug>`, which Django must accept.

        ALLOWED_HOSTS is matched exactly — the `<slug>.localhost` entry does
        not cover the bare `<slug>` a sibling project sends over the network
        alias, and without this the call fails with DisallowedHost (400).
        """
        _use_custom_project_name(tmp_path)
        (tmp_path / ".env").write_text("ALLOWED_HOSTS=localhost\nCSRF_TRUSTED_ORIGINS=http://localhost\n")

        with (
            patch("phoxtail.cli.net.check_compose_version", return_value=(True, "2.29.0")),
            patch("phoxtail.cli.net.slug_in_use_elsewhere", return_value=None),
            patch("phoxtail.cli.net.ensure_network"),
        ):
            result = runner.invoke(net_app, ["attach"])

        assert result.exit_code == 0, result.output
        hosts = _env_list((tmp_path / ".env").read_text(), "ALLOWED_HOSTS")
        assert "alphasite" in hosts, "bare slug missing — peer calls would 400"
        assert "alphasite.localhost" in hosts

    def test_points_api_url_at_the_project_hostname(self, tmp_path):
        """While attached, port 80 belongs to Traefik.

        `http://localhost` then reaches Traefik under a Host header no router
        claims and 404s, so every host-side API call breaks. The per-project
        hostname is routed correctly — and gives this project its own
        credential key instead of sharing the single `localhost` entry with
        every other project on the machine.
        """
        _use_custom_project_name(tmp_path)
        (tmp_path / ".env").write_text("ALLOWED_HOSTS=localhost\nCSRF_TRUSTED_ORIGINS=http://localhost\n")

        with (
            patch("phoxtail.cli.net.check_compose_version", return_value=(True, "2.29.0")),
            patch("phoxtail.cli.net.slug_in_use_elsewhere", return_value=None),
            patch("phoxtail.cli.net.ensure_network"),
        ):
            result = runner.invoke(net_app, ["attach"])

        assert result.exit_code == 0, result.output
        assert get_api_base_url() == "http://alphasite.localhost"

    def test_fragment_declares_slug_aliases_on_shared_network(self, tmp_path):
        """East-west addressing: peers reach this project by slug (§4.1).

        Both the bare slug and the dotted form are bound; the bare slug is
        the canonical peer address (see the template's own comment).
        """
        _use_custom_project_name(tmp_path)
        (tmp_path / ".env").write_text("ALLOWED_HOSTS=localhost\nCSRF_TRUSTED_ORIGINS=http://localhost\n")

        with (
            patch("phoxtail.cli.net.check_compose_version", return_value=(True, "2.29.0")),
            patch("phoxtail.cli.net.slug_in_use_elsewhere", return_value=None),
            patch("phoxtail.cli.net.ensure_network"),
        ):
            result = runner.invoke(net_app, ["attach"])

        assert result.exit_code == 0, result.output
        fragment = yaml.safe_load(_strip_reset_tags((tmp_path / "docker-compose.net.yaml").read_text()))

        web_networks = fragment["services"]["web"]["networks"]
        assert web_networks[NETWORK_NAME]["aliases"] == [
            "alphasite",
            "alphasite.localhost",
        ]

    def test_fragment_keeps_web_on_the_default_network(self, tmp_path):
        """Declaring any network replaces `web`'s implicit `default` membership.

        Dropping `default` here would silently cut `web` off from `db` and
        `redis`, which fails at runtime rather than at attach time.
        """
        _use_custom_project_name(tmp_path)
        (tmp_path / ".env").write_text("ALLOWED_HOSTS=localhost\nCSRF_TRUSTED_ORIGINS=http://localhost\n")

        with (
            patch("phoxtail.cli.net.check_compose_version", return_value=(True, "2.29.0")),
            patch("phoxtail.cli.net.slug_in_use_elsewhere", return_value=None),
            patch("phoxtail.cli.net.ensure_network"),
        ):
            runner.invoke(net_app, ["attach"])

        fragment = yaml.safe_load(_strip_reset_tags((tmp_path / "docker-compose.net.yaml").read_text()))
        assert "default" in fragment["services"]["web"]["networks"]

    def test_fragment_network_name_tracks_the_constant(self, tmp_path):
        """The network name is templated, not hardcoded — one rename, one edit."""
        _use_custom_project_name(tmp_path)
        (tmp_path / ".env").write_text("ALLOWED_HOSTS=localhost\nCSRF_TRUSTED_ORIGINS=http://localhost\n")

        with (
            patch("phoxtail.cli.net.check_compose_version", return_value=(True, "2.29.0")),
            patch("phoxtail.cli.net.slug_in_use_elsewhere", return_value=None),
            patch("phoxtail.cli.net.ensure_network"),
        ):
            runner.invoke(net_app, ["attach"])

        fragment = yaml.safe_load(_strip_reset_tags((tmp_path / "docker-compose.net.yaml").read_text()))
        assert fragment["networks"][NETWORK_NAME] == {"external": True}
        labels = fragment["services"]["web"]["labels"]
        assert f"traefik.docker.network={NETWORK_NAME}" in labels
        # The membership label is the source of truth for `slug_in_use_elsewhere`
        # and, later, for validating a peer target — so it must track the constant.
        assert f"{SLUG_LABEL}=alphasite" in labels

    def test_fragment_runs_the_projects_mcp_server(self, tmp_path):
        """Every attached project ships an always-on MCP service, so peers
        (and any MCP client) can run this project's tools in this project's
        own environment — the whole point of federation."""
        _use_custom_project_name(tmp_path)
        (tmp_path / ".env").write_text("ALLOWED_HOSTS=localhost\nCSRF_TRUSTED_ORIGINS=http://localhost\n")

        with (
            patch("phoxtail.cli.net.check_compose_version", return_value=(True, "2.29.0")),
            patch("phoxtail.cli.net.slug_in_use_elsewhere", return_value=None),
            patch("phoxtail.cli.net.ensure_network"),
        ):
            runner.invoke(net_app, ["attach"])

        fragment = yaml.safe_load(_strip_reset_tags((tmp_path / "docker-compose.net.yaml").read_text()))
        mcp = fragment["services"]["mcp"]

        # The service itself lives in the base compose file — the fragment
        # only re-addresses it: release the standalone port, claim the net
        # hostname. Port 80 keeps `mcp.<slug>.localhost` a single address for
        # both paths: Traefik's entrypoint from the host, the alias directly
        # from sibling containers.
        assert "image" not in mcp
        assert mcp["ports"] == []
        assert "default" in mcp["networks"]
        assert "mcp.alphasite.localhost" in mcp["networks"][NETWORK_NAME]["aliases"]
        labels = mcp["labels"]
        assert "traefik.http.routers.alphasite-mcp.rule=Host(`mcp.alphasite.localhost`)" in labels
        assert "traefik.http.services.alphasite-mcp.loadbalancer.server.port=80" in labels
        assert f"traefik.docker.network={NETWORK_NAME}" in labels

    def test_idempotent_rerun(self, tmp_path):
        _use_custom_project_name(tmp_path)
        (tmp_path / ".env").write_text("ALLOWED_HOSTS=localhost\nCSRF_TRUSTED_ORIGINS=http://localhost\n")

        with (
            patch("phoxtail.cli.net.check_compose_version", return_value=(True, "2.29.0")),
            patch("phoxtail.cli.net.slug_in_use_elsewhere", return_value=None),
            patch("phoxtail.cli.net.ensure_network"),
        ):
            runner.invoke(net_app, ["attach"])
            result = runner.invoke(net_app, ["attach"])

        assert result.exit_code == 0
        env_content = (tmp_path / ".env").read_text()
        assert env_content.count("alphasite.localhost") == 2  # ALLOWED_HOSTS + CSRF, each once

    def test_includes_existing_override_in_compose_file(self, tmp_path):
        _use_custom_project_name(tmp_path)
        (tmp_path / ".env").write_text("ALLOWED_HOSTS=localhost\nCSRF_TRUSTED_ORIGINS=http://localhost\n")
        (tmp_path / "docker-compose.override.yml").write_text("services: {}\n")

        with (
            patch("phoxtail.cli.net.check_compose_version", return_value=(True, "2.29.0")),
            patch("phoxtail.cli.net.slug_in_use_elsewhere", return_value=None),
            patch("phoxtail.cli.net.ensure_network"),
        ):
            result = runner.invoke(net_app, ["attach"])

        assert result.exit_code == 0
        env_content = (tmp_path / ".env").read_text()
        assert "COMPOSE_FILE=docker-compose.yaml:docker-compose.override.yml:docker-compose.net.yaml" in env_content

    def test_includes_override_with_yaml_spelling(self, tmp_path):
        """Compose auto-loads both spellings, so attach must carry both.

        Missing the `.yaml` one silently dropped the override — and with it
        the phoxtail bind-mounts dev projects rely on — because setting
        COMPOSE_FILE at all disables the automatic pickup.
        """
        _use_custom_project_name(tmp_path)
        (tmp_path / ".env").write_text("ALLOWED_HOSTS=localhost\nCSRF_TRUSTED_ORIGINS=http://localhost\n")
        (tmp_path / "docker-compose.override.yaml").write_text("services: {}\n")

        with (
            patch("phoxtail.cli.net.check_compose_version", return_value=(True, "2.29.0")),
            patch("phoxtail.cli.net.slug_in_use_elsewhere", return_value=None),
            patch("phoxtail.cli.net.ensure_network"),
        ):
            result = runner.invoke(net_app, ["attach"])

        assert result.exit_code == 0
        env_content = (tmp_path / ".env").read_text()
        assert "COMPOSE_FILE=docker-compose.yaml:docker-compose.override.yaml:docker-compose.net.yaml" in env_content

    def test_rerun_repairs_a_list_missing_the_override(self, tmp_path):
        """Re-running attach heals a project attached before its override was
        accounted for, keeping the net fragment last — later files win, and
        the fragment is the one that releases the ports to Traefik."""
        _use_custom_project_name(tmp_path)
        (tmp_path / ".env").write_text(
            "ALLOWED_HOSTS=localhost\n"
            "CSRF_TRUSTED_ORIGINS=http://localhost\n"
            "COMPOSE_FILE=docker-compose.yaml:docker-compose.net.yaml\n"
        )
        (tmp_path / "docker-compose.override.yaml").write_text("services: {}\n")

        with (
            patch("phoxtail.cli.net.check_compose_version", return_value=(True, "2.29.0")),
            patch("phoxtail.cli.net.slug_in_use_elsewhere", return_value=None),
            patch("phoxtail.cli.net.ensure_network"),
        ):
            result = runner.invoke(net_app, ["attach"])

        assert result.exit_code == 0
        env_content = (tmp_path / ".env").read_text()
        assert "COMPOSE_FILE=docker-compose.yaml:docker-compose.override.yaml:docker-compose.net.yaml" in env_content

    def test_rerun_preserves_hand_added_compose_files(self, tmp_path):
        _use_custom_project_name(tmp_path)
        (tmp_path / ".env").write_text(
            "ALLOWED_HOSTS=localhost\n"
            "CSRF_TRUSTED_ORIGINS=http://localhost\n"
            "COMPOSE_FILE=docker-compose.yaml:my-extras.yaml:docker-compose.net.yaml\n"
        )

        with (
            patch("phoxtail.cli.net.check_compose_version", return_value=(True, "2.29.0")),
            patch("phoxtail.cli.net.slug_in_use_elsewhere", return_value=None),
            patch("phoxtail.cli.net.ensure_network"),
        ):
            result = runner.invoke(net_app, ["attach"])

        assert result.exit_code == 0
        env_content = (tmp_path / ".env").read_text()
        assert "COMPOSE_FILE=docker-compose.yaml:my-extras.yaml:docker-compose.net.yaml" in env_content

    def test_attach_from_a_subdirectory_writes_at_the_project_root(self, tmp_path, monkeypatch):
        """find_config_file searches upward, so attach passes the project
        gate from a subdirectory — everything it writes must land next to
        phoxtail.toml, not in the cwd."""
        _use_custom_project_name(tmp_path)
        (tmp_path / ".env").write_text("ALLOWED_HOSTS=localhost\nCSRF_TRUSTED_ORIGINS=http://localhost\n")
        subdir = tmp_path / "apps"
        subdir.mkdir()
        monkeypatch.chdir(subdir)

        with (
            patch("phoxtail.cli.net.check_compose_version", return_value=(True, "2.29.0")),
            patch("phoxtail.cli.net.slug_in_use_elsewhere", return_value=None),
            patch("phoxtail.cli.net.ensure_network"),
        ):
            result = runner.invoke(net_app, ["attach"])

        assert result.exit_code == 0, result.output
        assert (tmp_path / "docker-compose.net.yaml").exists()
        assert not (subdir / "docker-compose.net.yaml").exists()
        assert not (subdir / ".env").exists()
        assert "COMPOSE_FILE=" in (tmp_path / ".env").read_text()

    def test_fails_loudly_when_docker_is_unavailable(self, tmp_path):
        """The guards shell out to docker; if that fails, attach must stop
        with the real error rather than writing a config that breaks at the
        next compose up."""
        _use_custom_project_name(tmp_path)
        with (
            patch("phoxtail.cli.net.check_compose_version", return_value=(True, "2.29.0")),
            patch(
                "phoxtail.cli.net.slug_in_use_elsewhere",
                side_effect=RuntimeError("Could not check slug ownership via docker ps: daemon down"),
            ),
        ):
            result = runner.invoke(net_app, ["attach"])
        assert result.exit_code == 1
        assert "daemon down" in result.output
        assert not (tmp_path / "docker-compose.net.yaml").exists()

    def test_never_touches_existing_override_file_contents(self, tmp_path):
        _use_custom_project_name(tmp_path)
        (tmp_path / ".env").write_text("ALLOWED_HOSTS=localhost\nCSRF_TRUSTED_ORIGINS=http://localhost\n")
        override_content = "# a hand-written comment\nservices:\n  web:\n    environment:\n      - FOO=bar\n"
        (tmp_path / "docker-compose.override.yml").write_text(override_content)

        with (
            patch("phoxtail.cli.net.check_compose_version", return_value=(True, "2.29.0")),
            patch("phoxtail.cli.net.slug_in_use_elsewhere", return_value=None),
            patch("phoxtail.cli.net.ensure_network"),
        ):
            runner.invoke(net_app, ["attach"])

        assert (tmp_path / "docker-compose.override.yml").read_text() == override_content


class TestAttachTokenWarning:
    """attach warns when no token is stored yet under the new credential key,
    so the operator knows the next step instead of hitting silent 401s."""

    def test_warns_when_no_token_stored(self, tmp_path):
        _use_custom_project_name(tmp_path)
        (tmp_path / ".env").write_text("ALLOWED_HOSTS=localhost\nCSRF_TRUSTED_ORIGINS=http://localhost\n")

        with (
            patch("phoxtail.cli.net.check_compose_version", return_value=(True, "2.29.0")),
            patch("phoxtail.cli.net.slug_in_use_elsewhere", return_value=None),
            patch("phoxtail.cli.net.ensure_network"),
            patch("phoxtail.cli.net.resolve_token", return_value=None),
        ):
            result = runner.invoke(net_app, ["attach"])

        assert result.exit_code == 0, result.output
        assert "No token stored" in result.output
        assert "phoxtail auth login" in result.output

    def test_no_warning_when_token_already_stored(self, tmp_path):
        _use_custom_project_name(tmp_path)
        (tmp_path / ".env").write_text("ALLOWED_HOSTS=localhost\nCSRF_TRUSTED_ORIGINS=http://localhost\n")

        with (
            patch("phoxtail.cli.net.check_compose_version", return_value=(True, "2.29.0")),
            patch("phoxtail.cli.net.slug_in_use_elsewhere", return_value=None),
            patch("phoxtail.cli.net.ensure_network"),
            patch("phoxtail.cli.net.resolve_token", return_value="phxt_abc"),
        ):
            result = runner.invoke(net_app, ["attach"])

        assert result.exit_code == 0, result.output
        assert "No token stored" not in result.output


class TestDetach:
    def test_reverses_attach(self, tmp_path):
        _use_custom_project_name(tmp_path)
        (tmp_path / ".env").write_text("ALLOWED_HOSTS=localhost\nCSRF_TRUSTED_ORIGINS=http://localhost\n")

        with (
            patch("phoxtail.cli.net.check_compose_version", return_value=(True, "2.29.0")),
            patch("phoxtail.cli.net.slug_in_use_elsewhere", return_value=None),
            patch("phoxtail.cli.net.ensure_network"),
        ):
            runner.invoke(net_app, ["attach"])

        result = runner.invoke(net_app, ["detach"])
        assert result.exit_code == 0
        assert not (tmp_path / "docker-compose.net.yaml").exists()

        env_content = (tmp_path / ".env").read_text()
        assert "alphasite" not in env_content
        # Exact lists, not substrings: a substring check would still pass with
        # the bare slug left behind as a trailing value. `web` survives detach
        # on purpose — the mcp service needs it attached or not.
        assert _env_list(env_content, "ALLOWED_HOSTS") == ["localhost", "web"]
        assert _env_list(env_content, "CSRF_TRUSTED_ORIGINS") == ["http://localhost"]
        # COMPOSE_FILE must be removed entirely, not left as "docker-compose.yaml":
        # Compose only auto-loads docker-compose.override.yml when COMPOSE_FILE is unset.
        assert "COMPOSE_FILE" not in env_content

    def test_restores_automatic_override_pickup(self, tmp_path):
        """COMPOSE_FILE left set (even to just the base file) suppresses Compose's
        automatic docker-compose.override.yml pickup, so detach must delete the key."""
        _use_custom_project_name(tmp_path)
        (tmp_path / ".env").write_text("ALLOWED_HOSTS=localhost\nCSRF_TRUSTED_ORIGINS=http://localhost\n")

        with (
            patch("phoxtail.cli.net.check_compose_version", return_value=(True, "2.29.0")),
            patch("phoxtail.cli.net.slug_in_use_elsewhere", return_value=None),
            patch("phoxtail.cli.net.ensure_network"),
        ):
            runner.invoke(net_app, ["attach"])
        runner.invoke(net_app, ["detach"])

        env_content = (tmp_path / ".env").read_text()
        assert not any(line.startswith("COMPOSE_FILE=") for line in env_content.splitlines())

    def test_noop_when_never_attached(self, tmp_path):
        _use_custom_project_name(tmp_path)
        result = runner.invoke(net_app, ["detach"])
        assert result.exit_code == 0


class TestRequiresProject:
    def test_attach_requires_phoxtail_toml(self, tmp_path, monkeypatch):
        (tmp_path / "phoxtail.toml").unlink()
        load_config.cache_clear()
        result = runner.invoke(net_app, ["attach"])
        assert result.exit_code == 1
        assert "Not a Phoxtail project" in result.output

    def test_detach_requires_phoxtail_toml(self, tmp_path, monkeypatch):
        (tmp_path / "phoxtail.toml").unlink()
        load_config.cache_clear()
        result = runner.invoke(net_app, ["detach"])
        assert result.exit_code == 1
        assert "Not a Phoxtail project" in result.output


def _members(*peers: Peer) -> list[Member]:
    """Members mirroring the given peers, for the ordinary all-attached case.

    `peers` merges two sources, so a test that patches only `list_peers`
    describes a project that is running but NOT attached — a real state, but
    not the one most of these tests are about.
    """
    return [Member(peer.working_dir or Path(f"/home/me/{peer.slug}"), peer.slug) for peer in peers]


class TestPeers:
    def test_lists_attached_projects_and_marks_this_one(self, tmp_path):
        _use_custom_project_name(tmp_path)
        peers = [
            Peer("alphasite", Path("/home/me/alphasite"), True),
            Peer("invoices-site", Path("/home/me/invoices"), False),
        ]
        with (
            patch("phoxtail.cli.net.list_peers", return_value=peers),
            patch("phoxtail.cli.net.read_members", return_value=_members(*peers)),
        ):
            result = runner.invoke(net_app, ["peers"])

        assert result.exit_code == 0, result.output
        assert "alphasite" in result.output
        assert "invoices-site" in result.output
        assert "this project" in result.output
        assert "running" in result.output and "stopped" in result.output

    def test_reports_empty_net_without_erroring(self, tmp_path):
        _use_custom_project_name(tmp_path)
        with patch("phoxtail.cli.net.list_peers", return_value=[]):
            result = runner.invoke(net_app, ["peers"])
        assert result.exit_code == 0
        assert "No projects attached" in result.output

    def test_json_output(self, tmp_path):
        _use_custom_project_name(tmp_path)
        peers = [
            Peer("alphasite", Path("/home/me/alphasite"), True),
            Peer("invoices-site", None, False),
        ]
        members = [Member(Path("/home/me/alphasite"), "alphasite"), Member(Path("/home/me/invoices"), "invoices-site")]
        with (
            patch("phoxtail.cli.net.list_peers", return_value=peers),
            patch("phoxtail.cli.net.read_members", return_value=members),
        ):
            result = runner.invoke(net_app, ["peers", "--json"])

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload == [
            {
                "slug": "alphasite",
                "address": "http://alphasite.localhost",
                "attached": True,
                "running": True,
                "working_dir": "/home/me/alphasite",
            },
            {
                "slug": "invoices-site",
                "address": "http://invoices-site.localhost",
                "attached": True,
                # The path of an attached project comes from its member entry,
                # not from the container — which is the point: a project with
                # no container at all still reports where it lives.
                "working_dir": "/home/me/invoices",
                "running": False,
            },
        ]

    def test_json_output_is_one_parseable_line_despite_long_paths(self, tmp_path):
        """Machine output must bypass Rich: its fold-wrapping breaks long
        unbroken tokens (a deep working_dir) with literal newlines, which
        lands *inside* a JSON string literal."""
        _use_custom_project_name(tmp_path)
        deep = Path("/home/me/" + "x" * 200)
        peer = Peer("invoices-site", deep, True)
        with (
            patch("phoxtail.cli.net.list_peers", return_value=[peer]),
            patch("phoxtail.cli.net.read_members", return_value=_members(peer)),
        ):
            result = runner.invoke(net_app, ["peers", "--json"])

        assert result.exit_code == 0, result.output
        assert result.output.strip().count("\n") == 0
        assert json.loads(result.output)[0]["working_dir"] == str(deep)

    def test_json_output_when_empty(self, tmp_path):
        _use_custom_project_name(tmp_path)
        with patch("phoxtail.cli.net.list_peers", return_value=[]):
            result = runner.invoke(net_app, ["peers", "--json"])
        assert result.exit_code == 0
        assert json.loads(result.output) == []

    def test_works_outside_a_project(self, tmp_path, monkeypatch):
        """The net is machine-wide, so `peers` must not require a phoxtail.toml.

        Covers the command's own handling of a missing config; the `"net"`
        entry in NO_PROJECT_COMMANDS that lets it past the main callback is
        registration, exercised in __main__ rather than here.
        """
        (tmp_path / "phoxtail.toml").unlink()
        load_config.cache_clear()
        peers = [Peer("invoices-site", Path("/home/me/invoices"), True)]
        with (
            patch("phoxtail.cli.net.list_peers", return_value=peers),
            patch("phoxtail.cli.net.read_members", return_value=_members(*peers)),
        ):
            result = runner.invoke(net_app, ["peers"])
        assert result.exit_code == 0, result.output
        assert "invoices-site" in result.output
        assert "this project" not in result.output


class TestApiUrlFollowsAttachment:
    """attach/detach own `api_url` because its correct value depends on them."""

    def _attach(self, tmp_path):
        (tmp_path / ".env").write_text("ALLOWED_HOSTS=localhost\nCSRF_TRUSTED_ORIGINS=http://localhost\n")
        with (
            patch("phoxtail.cli.net.check_compose_version", return_value=(True, "2.29.0")),
            patch("phoxtail.cli.net.slug_in_use_elsewhere", return_value=None),
            patch("phoxtail.cli.net.ensure_network"),
        ):
            return runner.invoke(net_app, ["attach"])

    def test_detach_restores_the_default(self, tmp_path):
        """Detached, the project publishes its own port 80 again."""
        _use_custom_project_name(tmp_path)
        self._attach(tmp_path)
        assert get_api_base_url() == "http://alphasite.localhost"

        result = runner.invoke(net_app, ["detach"])
        assert result.exit_code == 0, result.output
        assert get_api_base_url() == DEFAULT_API_BASE_URL

    def test_attach_then_detach_leaves_config_byte_identical(self, tmp_path):
        """Round-tripping must not perturb a file the user owns.

        Seeded with a `[studio] api_url` because that is what the project
        template ships — the realistic case. Byte-identity is only claimed
        when attach edits an existing key rather than creating the section.
        """
        (tmp_path / "phoxtail.toml").write_text(
            '# my notes\n[project]\nname = "alphasite"\napps = []\n\n[studio]\napi_url = "http://localhost"\n'
        )
        load_config.cache_clear()
        before = (tmp_path / "phoxtail.toml").read_text()

        self._attach(tmp_path)
        assert (tmp_path / "phoxtail.toml").read_text() != before

        runner.invoke(net_app, ["detach"])
        assert (tmp_path / "phoxtail.toml").read_text() == before

    def test_attach_is_idempotent_for_api_url(self, tmp_path):
        _use_custom_project_name(tmp_path)
        self._attach(tmp_path)
        first = (tmp_path / "phoxtail.toml").read_text()
        self._attach(tmp_path)
        assert (tmp_path / "phoxtail.toml").read_text() == first
        assert first.count("api_url") == 1


def _attached_dir(root: Path, wired: bool = True) -> Path:
    """A directory the fan-out will accept as a startable member."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "phoxtail.toml").write_text('[project]\nname = "x"\n')
    (root / "docker-compose.net.yaml").write_text("services: {}\n")
    listed = "docker-compose.yaml:docker-compose.net.yaml" if wired else "docker-compose.yaml"
    (root / ".env").write_text(f"COMPOSE_FILE={listed}\n")
    return root


class TestUpFansOutToProjects:
    """`net up` brings the whole net up: router first, then every member."""

    def _stack(self, tmp_path, monkeypatch):
        monkeypatch.setattr(net, "NET_DIR", tmp_path / "net")
        monkeypatch.setattr(net, "NET_COMPOSE_FILE", tmp_path / "net" / "docker-compose.yaml")

    def test_starts_each_member_in_its_own_directory(self, tmp_path, monkeypatch):
        """`cwd`, not `--project-directory`: the project's .env, build
        contexts and derived project name all resolve from there."""
        self._stack(tmp_path, monkeypatch)
        alpha = _attached_dir(tmp_path / "alpha")
        beta = _attached_dir(tmp_path / "beta")
        members = [Member(alpha, "alpha-site"), Member(beta, "beta-site")]

        with (
            patch("phoxtail.cli.net.ensure_network"),
            patch("phoxtail.cli.net.read_members", return_value=members),
            patch("phoxtail.cli.net.subprocess.call", return_value=0) as mock_call,
        ):
            result = runner.invoke(net_app, ["up"])

        assert result.exit_code == 0, result.output
        project_calls = [c for c in mock_call.call_args_list if c.kwargs.get("cwd")]
        assert [c.kwargs["cwd"] for c in project_calls] == [str(alpha), str(beta)]
        assert all(c.args[0] == ["docker", "compose", "up", "-d"] for c in project_calls)

    def test_router_starts_before_the_projects(self, tmp_path, monkeypatch):
        """A project started first would be unroutable until Traefik caught up."""
        self._stack(tmp_path, monkeypatch)
        members = [Member(_attached_dir(tmp_path / "alpha"), "alpha-site")]
        with (
            patch("phoxtail.cli.net.ensure_network"),
            patch("phoxtail.cli.net.read_members", return_value=members),
            patch("phoxtail.cli.net.subprocess.call", return_value=0) as mock_call,
        ):
            runner.invoke(net_app, ["up"])

        first, second = mock_call.call_args_list
        assert "-f" in first.args[0]  # the traefik stack
        assert second.kwargs["cwd"].endswith("alpha")

    def test_no_build_flag(self, tmp_path, monkeypatch):
        """Matching what the user types by hand — otherwise a first `net up`
        silently becomes a multi-minute image build."""
        self._stack(tmp_path, monkeypatch)
        members = [Member(_attached_dir(tmp_path / "alpha"), "alpha-site")]
        with (
            patch("phoxtail.cli.net.ensure_network"),
            patch("phoxtail.cli.net.read_members", return_value=members),
            patch("phoxtail.cli.net.subprocess.call", return_value=0) as mock_call,
        ):
            runner.invoke(net_app, ["up"])
        assert not any("--build" in c.args[0] for c in mock_call.call_args_list)

    def test_no_projects_flag_starts_only_the_router(self, tmp_path, monkeypatch):
        self._stack(tmp_path, monkeypatch)
        members = [Member(_attached_dir(tmp_path / "alpha"), "alpha-site")]
        with (
            patch("phoxtail.cli.net.ensure_network"),
            patch("phoxtail.cli.net.read_members", return_value=members),
            patch("phoxtail.cli.net.subprocess.call", return_value=0) as mock_call,
        ):
            result = runner.invoke(net_app, ["up", "--no-projects"])
        assert result.exit_code == 0
        assert mock_call.call_count == 1
        assert not any(c.kwargs.get("cwd") for c in mock_call.call_args_list)

    def test_skips_an_unwired_project_without_failing(self, tmp_path, monkeypatch):
        """Started from the base file alone it would publish its own port 80
        and fight Traefik for it — worse than not starting. The skip is a
        standing config fault, so it warns rather than failing the command."""
        self._stack(tmp_path, monkeypatch)
        broken = _attached_dir(tmp_path / "broken", wired=False)
        with (
            patch("phoxtail.cli.net.ensure_network"),
            patch("phoxtail.cli.net.read_members", return_value=[Member(broken, "broken-site")]),
            patch("phoxtail.cli.net.subprocess.call", return_value=0) as mock_call,
        ):
            result = runner.invoke(net_app, ["up"])

        assert result.exit_code == 0, result.output
        assert "skipped" in result.output
        assert "net attach" in result.output
        assert not any(c.kwargs.get("cwd") for c in mock_call.call_args_list)

    def test_continues_past_a_failing_project_and_exits_nonzero(self, tmp_path, monkeypatch):
        """One broken build must not strand every other project."""
        self._stack(tmp_path, monkeypatch)
        alpha = _attached_dir(tmp_path / "alpha")
        beta = _attached_dir(tmp_path / "beta")
        members = [Member(alpha, "alpha-site"), Member(beta, "beta-site")]

        def call(cmd, **kwargs):
            return 1 if kwargs.get("cwd") == str(alpha) else 0

        with (
            patch("phoxtail.cli.net.ensure_network"),
            patch("phoxtail.cli.net.read_members", return_value=members),
            patch("phoxtail.cli.net.subprocess.call", side_effect=call) as mock_call,
        ):
            result = runner.invoke(net_app, ["up"])

        assert result.exit_code == 1
        assert [c.kwargs["cwd"] for c in mock_call.call_args_list if c.kwargs.get("cwd")] == [str(alpha), str(beta)]
        assert "alpha-site" in result.output

    def test_strips_compose_env_that_would_override_each_project(self, tmp_path, monkeypatch):
        """A real env var outranks a project's .env. Exported in the caller's
        shell these describe ONE project; inherited here they would override
        the COMPOSE_FILE just verified, or start every project's services
        under a single shared project name."""
        self._stack(tmp_path, monkeypatch)
        monkeypatch.setenv("COMPOSE_FILE", "/somewhere/else.yaml")
        monkeypatch.setenv("COMPOSE_PROJECT_NAME", "the-callers-project")
        members = [Member(_attached_dir(tmp_path / "alpha"), "alpha-site")]

        with (
            patch("phoxtail.cli.net.ensure_network"),
            patch("phoxtail.cli.net.read_members", return_value=members),
            patch("phoxtail.cli.net.subprocess.call", return_value=0) as mock_call,
        ):
            runner.invoke(net_app, ["up"])

        env = next(c for c in mock_call.call_args_list if c.kwargs.get("cwd")).kwargs["env"]
        assert "COMPOSE_FILE" not in env
        assert "COMPOSE_PROJECT_NAME" not in env
        assert "HOST_UID" in env  # the reason docker_env() exists at all


class TestDownFansOutToProjects:
    def _stack(self, tmp_path, monkeypatch):
        compose_file = tmp_path / "net" / "docker-compose.yaml"
        compose_file.parent.mkdir(parents=True, exist_ok=True)
        compose_file.write_text("services: {}\n")
        monkeypatch.setattr(net, "NET_COMPOSE_FILE", compose_file)
        return compose_file

    def test_stops_projects_before_the_router(self, tmp_path, monkeypatch):
        """The reverse order would leave every project running but
        unroutable — the worst intermediate state to be interrupted in."""
        compose_file = self._stack(tmp_path, monkeypatch)
        alpha = _attached_dir(tmp_path / "alpha")
        with (
            patch("phoxtail.cli.net.read_members", return_value=[Member(alpha, "alpha-site")]),
            patch("phoxtail.cli.net.subprocess.call", return_value=0) as mock_call,
        ):
            result = runner.invoke(net_app, ["down"])

        assert result.exit_code == 0, result.output
        first, second = mock_call.call_args_list
        assert first.kwargs["cwd"] == str(alpha)
        assert second.args[0] == ["docker", "compose", "-f", str(compose_file), "down"]

    def test_stops_rather_than_removes_by_default(self, tmp_path, monkeypatch):
        """`stop` keeps the containers, so `peers` still reports the project
        as stopped and a restart is quick."""
        self._stack(tmp_path, monkeypatch)
        alpha = _attached_dir(tmp_path / "alpha")
        with (
            patch("phoxtail.cli.net.read_members", return_value=[Member(alpha, "alpha-site")]),
            patch("phoxtail.cli.net.subprocess.call", return_value=0) as mock_call,
        ):
            runner.invoke(net_app, ["down"])
        assert mock_call.call_args_list[0].args[0] == ["docker", "compose", "stop"]

    def test_remove_flag_tears_the_projects_down(self, tmp_path, monkeypatch):
        self._stack(tmp_path, monkeypatch)
        alpha = _attached_dir(tmp_path / "alpha")
        with (
            patch("phoxtail.cli.net.read_members", return_value=[Member(alpha, "alpha-site")]),
            patch("phoxtail.cli.net.subprocess.call", return_value=0) as mock_call,
        ):
            runner.invoke(net_app, ["down", "--remove"])
        assert mock_call.call_args_list[0].args[0] == ["docker", "compose", "down"]

    def test_no_projects_flag_stops_only_the_router(self, tmp_path, monkeypatch):
        self._stack(tmp_path, monkeypatch)
        alpha = _attached_dir(tmp_path / "alpha")
        with (
            patch("phoxtail.cli.net.read_members", return_value=[Member(alpha, "alpha-site")]),
            patch("phoxtail.cli.net.subprocess.call", return_value=0) as mock_call,
        ):
            result = runner.invoke(net_app, ["down", "--no-projects"])
        assert result.exit_code == 0
        assert mock_call.call_count == 1
        assert not any(c.kwargs.get("cwd") for c in mock_call.call_args_list)

    def test_exits_nonzero_when_a_project_fails(self, tmp_path, monkeypatch):
        self._stack(tmp_path, monkeypatch)
        alpha = _attached_dir(tmp_path / "alpha")
        with (
            patch("phoxtail.cli.net.read_members", return_value=[Member(alpha, "alpha-site")]),
            patch("phoxtail.cli.net.subprocess.call", side_effect=lambda cmd, **kw: 1 if kw.get("cwd") else 0),
        ):
            result = runner.invoke(net_app, ["down"])
        assert result.exit_code == 1

    def test_still_stops_projects_when_the_net_was_never_set_up(self, tmp_path, monkeypatch):
        """Projects can be attached and running with no Traefik stack file —
        the absent router must not skip stopping them."""
        monkeypatch.setattr(net, "NET_COMPOSE_FILE", tmp_path / "net" / "docker-compose.yaml")
        alpha = _attached_dir(tmp_path / "alpha")
        with (
            patch("phoxtail.cli.net.read_members", return_value=[Member(alpha, "alpha-site")]),
            patch("phoxtail.cli.net.subprocess.call", return_value=0) as mock_call,
        ):
            result = runner.invoke(net_app, ["down"])
        assert result.exit_code == 0
        assert mock_call.call_count == 1
        assert mock_call.call_args_list[0].kwargs["cwd"] == str(alpha)


class TestPeersStates:
    """`peers` is the one place the two sources are merged, so it is the one
    place all four states are visible."""

    def _invoke(self, members, peers, args=None):
        with (
            patch("phoxtail.cli.net.read_members", return_value=members),
            patch("phoxtail.cli.net.list_peers", return_value=peers),
        ):
            return runner.invoke(net_app, ["peers", *(args or [])])

    def test_attached_with_no_container_reads_not_created(self, tmp_path):
        """`docker compose down` deletes the container carrying the label.
        Before the members file this project vanished from the list."""
        result = self._invoke([Member(Path("/home/me/alpha"), "alpha-site")], [])
        assert result.exit_code == 0, result.output
        assert "not created" in result.output
        assert "alpha-site" in result.output

    def test_attached_and_exited_reads_stopped(self, tmp_path):
        members = [Member(Path("/home/me/alpha"), "alpha-site")]
        peers = [Peer("alpha-site", Path("/home/me/alpha"), False)]
        assert "stopped" in self._invoke(members, peers).output

    def test_attached_and_live_reads_running(self, tmp_path):
        members = [Member(Path("/home/me/alpha"), "alpha-site")]
        peers = [Peer("alpha-site", Path("/home/me/alpha"), True)]
        assert "running" in self._invoke(members, peers).output

    def test_labelled_container_of_a_detached_project_reads_detached(self, tmp_path):
        """`detach` edits files; the label was stamped at container creation
        and outlives it. Hiding the row would leave a name that still routes
        unexplained — showing it as detached is the honest answer."""
        result = self._invoke([], [Peer("ghost-site", Path("/home/me/ghost"), True)])
        assert "detached" in result.output
        assert "ghost-site" in result.output
        assert "docker compose up -d" in result.output  # how to clear it

    def test_detached_row_is_absent_when_everything_agrees(self, tmp_path):
        members = [Member(Path("/home/me/alpha"), "alpha-site")]
        peers = [Peer("alpha-site", Path("/home/me/alpha"), True)]
        assert "detached" not in self._invoke(members, peers).output

    def test_path_of_an_attached_project_comes_from_the_members_file(self, tmp_path):
        """Which is the point: a project with no container still reports
        where it lives, so `net up` can be told what it would start."""
        members = [Member(Path("/home/me/alpha"), "alpha-site")]
        payload = json.loads(self._invoke(members, [], ["--json"]).output)
        assert payload == [
            {
                "slug": "alpha-site",
                "address": "http://alpha-site.localhost",
                "attached": True,
                "running": False,
                "working_dir": "/home/me/alpha",
            }
        ]

    def test_json_marks_a_detached_container(self, tmp_path):
        payload = json.loads(self._invoke([], [Peer("ghost-site", None, True)], ["--json"]).output)
        assert payload[0]["attached"] is False
        assert payload[0]["running"] is True
        assert payload[0]["working_dir"] is None

    def test_slug_markup_parses_as_a_hyperlink(self, tmp_path):
        """A non-tty drops the OSC 8 escape, so what this pins is that the
        markup is well formed — a malformed `[link=...]` would survive into
        the output literally."""
        members = [Member(Path("/home/me/alpha"), "alpha-site")]
        output = self._invoke(members, []).output
        assert "[link=" not in output
        assert "http://alpha-site.localhost" not in output


class TestAttachRecordsMembership:
    def test_attach_records_the_project(self, tmp_path):
        _use_custom_project_name(tmp_path)
        (tmp_path / ".env").write_text("ALLOWED_HOSTS=localhost\n")
        with (
            patch("phoxtail.cli.net.check_compose_version", return_value=(True, "2.29.0")),
            patch("phoxtail.cli.net.slug_in_use_elsewhere", return_value=None),
            patch("phoxtail.cli.net.ensure_network"),
        ):
            result = runner.invoke(net_app, ["attach"])

        assert result.exit_code == 0, result.output
        assert read_members() == [Member(tmp_path.resolve(), "alphasite")]

    def test_attach_is_repeatable_without_duplicating_the_entry(self, tmp_path):
        _use_custom_project_name(tmp_path)
        (tmp_path / ".env").write_text("ALLOWED_HOSTS=localhost\n")
        with (
            patch("phoxtail.cli.net.check_compose_version", return_value=(True, "2.29.0")),
            patch("phoxtail.cli.net.slug_in_use_elsewhere", return_value=None),
            patch("phoxtail.cli.net.ensure_network"),
        ):
            runner.invoke(net_app, ["attach"])
            runner.invoke(net_app, ["attach"])

        assert len(read_members()) == 1

    def test_detach_ends_membership_immediately(self, tmp_path):
        """Not when the container is recreated: the label lingers until the
        next `up`, so Docker keeps reporting the project. The members file is
        what makes `peers` and `net up` follow the user's intent at once."""
        _use_custom_project_name(tmp_path)
        (tmp_path / ".env").write_text("ALLOWED_HOSTS=localhost\n")
        with (
            patch("phoxtail.cli.net.check_compose_version", return_value=(True, "2.29.0")),
            patch("phoxtail.cli.net.slug_in_use_elsewhere", return_value=None),
            patch("phoxtail.cli.net.ensure_network"),
        ):
            runner.invoke(net_app, ["attach"])
        assert read_members() != []

        result = runner.invoke(net_app, ["detach"])
        assert result.exit_code == 0, result.output
        assert read_members() == []

    def test_no_member_recorded_when_a_later_step_fails(self, tmp_path):
        """Membership is written last, once nothing left can fail. Recorded
        earlier, a failing .gitignore append would leave an entry behind and
        `net up` would start a project the user was told did not attach."""
        _use_custom_project_name(tmp_path)
        (tmp_path / ".env").write_text("ALLOWED_HOSTS=localhost\n")
        # A directory named .gitignore: `exists()` passes, reading it raises.
        # A real failure rather than a mock — patching Path.open would break
        # read_text/write_text too and blow up long before this point, so the
        # test would pass without ever reaching the ordering it checks.
        (tmp_path / ".gitignore").mkdir()

        with (
            patch("phoxtail.cli.net.check_compose_version", return_value=(True, "2.29.0")),
            patch("phoxtail.cli.net.slug_in_use_elsewhere", return_value=None),
            patch("phoxtail.cli.net.ensure_network"),
        ):
            result = runner.invoke(net_app, ["attach"])

        # Pin *why* it failed. A non-zero exit alone would also be satisfied
        # by attach failing earlier for an unrelated reason, leaving the test
        # green while never reaching the ordering it exists to check.
        assert isinstance(result.exception, IsADirectoryError), result.output
        assert result.exit_code != 0
        assert read_members() == []

    def test_gitignore_is_updated_before_membership_is_recorded(self, tmp_path):
        """The ordering above must not have cost the gitignore entry."""
        _use_custom_project_name(tmp_path)
        (tmp_path / ".env").write_text("ALLOWED_HOSTS=localhost\n")
        (tmp_path / ".gitignore").write_text("*.pyc\n")

        with (
            patch("phoxtail.cli.net.check_compose_version", return_value=(True, "2.29.0")),
            patch("phoxtail.cli.net.slug_in_use_elsewhere", return_value=None),
            patch("phoxtail.cli.net.ensure_network"),
        ):
            result = runner.invoke(net_app, ["attach"])

        assert result.exit_code == 0, result.output
        assert "docker-compose.net.yaml" in (tmp_path / ".gitignore").read_text()
        assert read_members() == [Member(tmp_path.resolve(), "alphasite")]
