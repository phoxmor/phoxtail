"""Shared local network utilities: the Traefik stack, membership, env editing."""

import json
import os
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

NET_DIR = Path.home() / ".phoxtail" / "net"
NET_COMPOSE_FILE = NET_DIR / "docker-compose.yaml"
NETWORK_NAME = "phoxtail-net"
PROJECT_NET_FILE = "docker-compose.net.yaml"
SLUG_LABEL = "phoxtail.slug"
MIN_COMPOSE_VERSION = (2, 24)


def network_exists() -> bool:
    result = subprocess.run(
        ["docker", "network", "inspect", NETWORK_NAME],
        capture_output=True,
    )
    return result.returncode == 0


def ensure_network() -> None:
    """Create the shared network if absent; raise if Docker can't.

    A swallowed failure here would let ``attach`` report success against a
    network that doesn't exist, deferring the error to the next
    ``docker compose up`` with a far less helpful message.
    """
    if network_exists():
        return
    result = subprocess.run(
        ["docker", "network", "create", NETWORK_NAME],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or "is Docker running?"
        raise RuntimeError(f"Could not create the {NETWORK_NAME} network: {detail}")


def net_stack_running() -> bool:
    if not NET_COMPOSE_FILE.exists():
        return False
    result = subprocess.run(
        ["docker", "compose", "-f", str(NET_COMPOSE_FILE), "ps", "--status", "running", "--services"],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0 and "traefik" in result.stdout.split()


def check_compose_version() -> tuple[bool, str]:
    """Return (meets_minimum, raw_version_string).

    Raw version is "unknown" if it couldn't be determined at all, in which
    case meets_minimum is False.
    """
    result = subprocess.run(["docker", "compose", "version", "--short"], capture_output=True, text=True)
    if result.returncode != 0:
        return False, "unknown"
    raw = result.stdout.strip()
    parts = raw.lstrip("v").split(".")
    try:
        major, minor = int(parts[0]), int(parts[1])
    except (IndexError, ValueError):
        return False, raw
    return (major, minor) >= MIN_COMPOSE_VERSION, raw


@dataclass(frozen=True)
class Peer:
    """A project attached to the shared net, as Docker reports it."""

    slug: str
    working_dir: Path | None
    running: bool

    @property
    def hostname(self) -> str:
        return f"{self.slug}.localhost"

    @property
    def address(self) -> str:
        """The one URL that reaches this peer from anywhere.

        `<slug>.localhost` works from the host (resolves to loopback, where
        Traefik routes it by Host header) *and* from inside a sibling
        container (the network alias claims the same name). The bare `<slug>`
        alias is also bound, but only resolves container-side — so it cannot
        be the canonical form, and it would key credentials differently.

        Callers must check the peer exists before using this. Docker's DNS
        answers an *unclaimed* `*.localhost` with loopback rather than a
        failure, so an unknown name silently reaches the caller itself.
        :func:`list_peers` is the check.
        """
        return f"http://{self.hostname}"

    @property
    def mcp_url(self) -> str:
        """The peer's MCP server endpoint, host- and container-reachable.

        `mcp.<slug>.localhost` follows the same one-name principle as
        :attr:`address`: from the host, Traefik routes it by Host header to
        the peer's `mcp` service; inside containers, the network alias
        claims the same name (with the service listening on port 80 so no
        port differs between the two paths). Credentials are NOT keyed by
        this host — callers authenticate with the token stored for
        :attr:`address`, which the peer's MCP server forwards to its API.
        """
        return f"http://mcp.{self.hostname}/mcp"


def _peers_from_traefik() -> list[Peer]:
    """Peer discovery for environments without a docker CLI — i.e. inside a
    project container, where the chatbot agent runs.

    Traefik's router table is built from the same container labels the docker
    path reads, so this is the same single source of truth through a
    different window. Differences are inherent to that window: only running
    projects appear (Traefik routes live containers only), and working
    directories are unknown.

    The request goes to the compose service name ``traefik``, which Docker's
    DNS resolves for every container on the shared network. It must NOT go
    to ``traefik.localhost``: that name is a router *rule*, not a network
    alias, so in-container it is an unclaimed ``*.localhost`` and resolves
    to loopback — the caller itself. The Host header still has to carry the
    dashboard hostname, because the api@internal service is only routed
    under that rule.
    """
    import httpx

    try:
        resp = httpx.get(
            "http://traefik/api/http/routers",
            headers={"Host": "traefik.localhost"},
            timeout=2.0,
        )
        resp.raise_for_status()
        routers = resp.json()
    except Exception:
        # Traefik unreachable means this container is not on the shared net
        # (or the net is down) — either way no peer can be reached.
        return []

    peers: dict[str, Peer] = {}
    for router in routers:
        # A peer is exactly one label before .localhost: subdomain routers
        # (`mcp.<slug>.localhost`) are a project's *services*, not projects,
        # and the dashboard's `traefik.localhost` is infrastructure.
        match = re.fullmatch(r"Host\(`([^.`]+)\.localhost`\)", router.get("rule", ""))
        if match is None or match.group(1) == "traefik":
            continue
        peers[match.group(1)] = Peer(match.group(1), None, True)
    return sorted(peers.values(), key=lambda p: p.slug)


def list_peers() -> list[Peer]:
    """Return every project Docker can currently see on the shared net.

    This answers *reachability*, never membership — :func:`read_members`
    answers membership, and the two must not be merged. The ``phoxtail.slug``
    label is stamped on the container when it is **created**, so it is a
    snapshot of the last ``up``, not a live fact: ``detach`` leaves it on an
    existing container, and ``down`` deletes the container that carried it.

    Keeping this function on the Docker side of that split is what protects
    :func:`resolve_peer` — a caller must never be handed an address it cannot
    reach, because an unclaimed ``*.localhost`` resolves to loopback instead
    of failing.
    """
    fmt = f'{{{{.Label "{SLUG_LABEL}"}}}}\t{{{{.Label "com.docker.compose.project.working_dir"}}}}\t{{{{.State}}}}'
    try:
        result = subprocess.run(
            ["docker", "ps", "-a", "--filter", f"label={SLUG_LABEL}", "--format", fmt],
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return _peers_from_traefik()
    if result.returncode != 0:
        return []

    peers: dict[str, Peer] = {}
    for line in result.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) != 3 or not parts[0].strip():
            continue
        slug, working_dir, state = (p.strip() for p in parts)
        running = state == "running"
        existing = peers.get(slug)
        # A slug can appear on several containers (e.g. an old exited one).
        # Prefer a running container so the report reflects what is reachable.
        if existing is None or (running and not existing.running):
            peers[slug] = Peer(slug, Path(working_dir) if working_dir else None, running)
    return sorted(peers.values(), key=lambda p: p.slug)


@dataclass(frozen=True)
class Member:
    """A project this machine has attached to the shared net.

    Membership, written by ``attach`` and erased by ``detach`` — as opposed to
    :class:`Peer`, which is reachability read from Docker. The two disagree
    exactly where it matters: an attached project that has been ``down``ed is
    a Member and not a Peer; a detached project whose old container still
    carries the label is a Peer and not a Member.
    """

    root: Path
    slug: str

    @property
    def hostname(self) -> str:
        return f"{self.slug}.localhost"

    @property
    def address(self) -> str:
        """Where this project answers once it is up — see :attr:`Peer.address`.

        A member is not necessarily reachable, so this is the address it
        *claims*, not one that has been checked. Route calls through
        :func:`resolve_peer`, never through here.
        """
        return f"http://{self.hostname}"


def members_file() -> Path:
    """Path to the members file, resolved on each call.

    Deliberately a function, not a module constant: a constant would bind
    ``NET_DIR`` at import, so a test redirecting ``NET_DIR`` to a temp dir
    would still have ``add_member`` writing the real
    ``~/.phoxtail/net/members.json``. One monkeypatch of ``NET_DIR`` now
    redirects every read and write here.
    """
    return NET_DIR / "members.json"


def is_wired(root: Path) -> bool:
    """Whether *root*'s ``.env`` actually loads the net fragment.

    The fragment existing on disk is not enough: Compose only reads it when
    ``COMPOSE_FILE`` lists it. A project that lost that line starts from the
    base compose file alone, publishes its own port 80, and fights Traefik
    for it — so starting it is worse than skipping it.
    """
    env_file = root / ".env"
    if not env_file.exists():
        return False
    return any(
        line.startswith("COMPOSE_FILE=") and PROJECT_NET_FILE in line for line in env_file.read_text().splitlines()
    )


def _attachment_intact(root: Path) -> bool:
    """Whether *root* still looks like a project that was attached.

    Both files are ``attach`` output and ``detach`` removes the fragment, so
    this doubles as the prune rule: an entry failing it was deleted, moved,
    or detached by something that never told the members file.
    """
    return (root / "phoxtail.toml").exists() and (root / PROJECT_NET_FILE).exists()


def _members_from_containers() -> list[Member]:
    """Recover membership from container labels when no members file exists.

    A one-time migration for projects attached before the members file existed —
    without it their first ``net up`` would find nothing to start. Containers
    carry ``com.docker.compose.project.working_dir``, which *is* the project
    root, and :func:`_attachment_intact` filters out the ones that have since
    detached but kept a stale labelled container.

    Yields nothing in-container, where ``list_peers`` falls back to Traefik
    and no working dir is known. That is correct: membership is host-side
    state and containers cannot read it anyway.
    """
    recovered: dict[Path, Member] = {}
    for peer in list_peers():
        if peer.working_dir is None or not _attachment_intact(peer.working_dir):
            continue
        # Resolved to match `add_member`, so a symlinked path recovered here
        # and the same project attached later are one entry, not two.
        root = peer.working_dir.resolve()
        recovered[root] = Member(root, peer.slug)
    return sorted(recovered.values(), key=lambda m: m.slug)


def read_members() -> list[Member]:
    """Return every project attached to the shared net, per this machine's record.

    Prunes entries whose project no longer looks attached, so the file
    self-heals without a GC command — stale rows never survive the write that
    follows. Unreadable or missing content reads as empty rather than raising:
    every caller is a CLI command that must still work when the shared net has
    never been set up.
    """
    path = members_file()
    if not path.exists():
        return _members_from_containers()

    try:
        entries = json.loads(path.read_text())["projects"]
    except (OSError, ValueError, KeyError, TypeError):
        return []

    members: dict[Path, Member] = {}
    for entry in entries:
        try:
            root = Path(entry["root"]).resolve()
            slug = str(entry["slug"])
        except (KeyError, TypeError, OSError):
            continue
        if _attachment_intact(root):
            members[root] = Member(root, slug)
    return sorted(members.values(), key=lambda m: m.slug)


def _write_members(members: list[Member]) -> None:
    NET_DIR.mkdir(parents=True, exist_ok=True)
    payload = {"projects": [{"root": str(m.root), "slug": m.slug} for m in members]}

    # Write-then-rename: a crash partway through a plain write would leave
    # truncated JSON, which reads as "nothing is attached" — silently turning
    # the next `net up` into a no-op rather than an error anyone would notice.
    fd, tmp = tempfile.mkstemp(dir=NET_DIR, prefix=".members-", suffix=".json")
    try:
        with os.fdopen(fd, "w") as handle:
            handle.write(json.dumps(payload, indent=2) + "\n")
        os.replace(tmp, members_file())
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def add_member(root: Path, slug: str) -> None:
    """Record *root* as attached under *slug*, replacing any earlier entry for it.

    Keyed by root, not slug: the directory is the stable identity, while a
    slug changes the moment someone edits ``[project] name`` in phoxtail.toml.
    """
    root = root.resolve()
    members = [m for m in read_members() if m.root != root]
    members.append(Member(root, slug))
    _write_members(sorted(members, key=lambda m: m.slug))


def remove_member(root: Path) -> None:
    """Drop *root* from the members file. Safe when it was never in it."""
    root = root.resolve()
    _write_members([m for m in read_members() if m.root != root])


def slug_in_use_elsewhere(slug: str, project_root: Path) -> Path | None:
    """Return the working dir of another project already attached under this slug, if any.

    *project_root* — not the cwd — is what "this project" means: the
    directory holding phoxtail.toml, which is also the compose working dir
    Docker records. Comparing against the cwd would make a re-attach from a
    subdirectory collide with the project itself.

    Raises :class:`RuntimeError` when ``docker ps`` itself fails: a guard
    that silently passes when Docker is down isn't a guard.

    Checks the members file first, because Docker alone cannot see a project
    that is attached but has no container: ``down`` deletes the container
    carrying the slug label, so a second project could take the same slug
    unwarned — and ``net up`` would then start both, each claiming
    ``Host(`<slug>.localhost`)`` for Traefik to choose between arbitrarily.
    """
    root = project_root.resolve()
    for member in read_members():
        if member.slug == slug and member.root != root:
            return member.root

    result = subprocess.run(
        [
            "docker",
            "ps",
            "-a",
            "--filter",
            f"label={SLUG_LABEL}={slug}",
            "--format",
            '{{.Label "com.docker.compose.project.working_dir"}}',
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or "is Docker running?"
        raise RuntimeError(f"Could not check slug ownership via docker ps: {detail}")
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        other = Path(line).resolve()
        if other != root:
            return other
    return None


class UnknownPeer(LookupError):
    """Raised when a peer slug matches no project attached to the shared net."""


class PeerNotRunning(UnknownPeer):
    """Raised when a peer exists but has no running container to answer.

    Subclasses :class:`UnknownPeer` so existing callers keep handling it —
    the distinction is the *message*, which must name the real problem.
    """


def resolve_peer(slug: str) -> Peer:
    """Return the :class:`Peer` for *slug*, or raise :class:`UnknownPeer`.

    Never skip this check before addressing a peer. Docker's embedded DNS
    answers an *unclaimed* ``*.localhost`` with loopback rather than a
    resolution failure, so an unknown or misspelled slug does not fail — it
    silently reaches the caller's own project, which then rejects the
    unexpected Host header with a 400. Measured with a one-character typo:
    ``phoxtail-invoice-site`` returned ``400`` from the *caller's* own
    WSGIServer, an error naming entirely the wrong problem.

    The exception lists the attached peers so the caller — often an LLM that
    guessed the name — can correct itself.
    """
    slug = (slug or "").strip()
    peers = list_peers()
    for peer in peers:
        if peer.slug == slug:
            # A stopped peer is listed (``docker ps -a`` includes exited
            # containers) but Traefik only routes live ones, so its hostname
            # is an *unclaimed* `*.localhost` — the same loopback trap as a
            # typo, reached by a correctly spelled name. Refusing here is
            # what makes the caller see "it is stopped" instead of a 400 from
            # its own Django.
            if not peer.running:
                where = f" in {peer.working_dir}" if peer.working_dir else ""
                raise PeerNotRunning(
                    f"Project {slug!r} is on the shared net but has no running container, "
                    f"so it cannot answer. Start it with `docker compose up -d`{where}, "
                    f"or bring the whole net up with `phoxtail net up`."
                )
            return peer

    known = ", ".join(p.slug for p in peers) or "none (is anything attached?)"
    raise UnknownPeer(f"No project named {slug!r} is attached to the shared net. Attached peers: {known}.")


def set_api_url(path: Path, url: str) -> None:
    """Point ``[studio] api_url`` at *url* in phoxtail.toml, leaving the rest alone.

    Hand-edited rather than round-tripped through a TOML library: ``tomllib``
    is read-only, and rewriting the file from parsed data would discard the
    comments and ordering the user put there.

    ``api_url`` tracks attachment state, which is why ``attach``/``detach``
    own it. Unattached, a project publishes its own port 80 and
    ``http://localhost`` is correct. Attached, that port is released to
    Traefik and ``http://localhost`` reaches Traefik with a Host header no
    router claims — a 404. The per-project hostname is right in both
    directions and, as a bonus, gives each project a distinct credential key
    instead of every project sharing the single ``localhost`` entry.
    """
    lines = path.read_text().splitlines() if path.exists() else []
    new_line = f'api_url = "{url}"'

    # Only the `api_url` inside [studio] is ours to edit: an identically
    # named key in some other section belongs to whoever put it there.
    section = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("["):
            section = stripped
        elif section == "[studio]" and stripped.startswith("api_url"):
            indent = line[: len(line) - len(line.lstrip())]
            lines[i] = indent + new_line
            break
    else:
        if not any(line.strip() == "[studio]" for line in lines):
            if lines and lines[-1].strip():
                lines.append("")
            lines.append("[studio]")
            lines.append(new_line)
        else:
            insert_at = next(i for i, line in enumerate(lines) if line.strip() == "[studio]") + 1
            lines.insert(insert_at, new_line)

    path.write_text("\n".join(lines) + "\n")


def _split_nonempty(value: str, sep: str) -> list[str]:
    return [v for v in (part.strip() for part in value.split(sep)) if v]


def upsert_env_list(path: Path, key: str, value: str, sep: str) -> None:
    """Ensure ``value`` is present in the ``sep``-delimited list at ``KEY=`` in an env file.

    Preserves every other line untouched. Appends a new ``KEY=value`` line
    if the key isn't present at all, and creates the file if missing.
    """
    prefix = f"{key}="
    lines = path.read_text().splitlines() if path.exists() else []

    for i, line in enumerate(lines):
        if line.startswith(prefix):
            current = _split_nonempty(line[len(prefix) :], sep)
            if value not in current:
                current.append(value)
            lines[i] = prefix + sep.join(current)
            break
    else:
        lines.append(prefix + value)

    path.write_text("\n".join(lines) + "\n")


def remove_env_key(path: Path, key: str) -> None:
    """Delete the whole ``KEY=...`` line from an env file, if present.

    Unlike removing one value from a list, this drops the key entirely.
    Needed for COMPOSE_FILE specifically: Compose only auto-loads
    docker-compose.override.yml when COMPOSE_FILE is *unset* — leaving it
    set to just the base file, even with nothing extra in the list, still
    suppresses that automatic pickup.
    """
    if not path.exists():
        return

    prefix = f"{key}="
    lines = [line for line in path.read_text().splitlines() if not line.startswith(prefix)]
    path.write_text("\n".join(lines) + "\n")


def remove_env_list_value(path: Path, key: str, value: str, sep: str) -> None:
    """Inverse of upsert_env_list: drop ``value`` from the list at ``KEY=`` if present."""
    if not path.exists():
        return

    prefix = f"{key}="
    lines = path.read_text().splitlines()

    for i, line in enumerate(lines):
        if line.startswith(prefix):
            current = _split_nonempty(line[len(prefix) :], sep)
            current = [v for v in current if v != value]
            lines[i] = prefix + sep.join(current)
            break

    path.write_text("\n".join(lines) + "\n")
