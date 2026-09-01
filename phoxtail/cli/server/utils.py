"""Shared helpers for server commands — SSH, git, cloud-init, formatting."""

import subprocess
import time
from pathlib import Path

import typer
from rich.console import Console

from phoxtail.cli.server.providers.base import SSHKey
from phoxtail.cli.utils.config import get_project_name, slugify
from phoxtail.cli.utils.templates import render_template

# ------------------------------------------------------------------
# Formatting helpers
# ------------------------------------------------------------------


def fmt_memory(gb: float) -> str:
    return f"{int(gb)} GB" if gb == int(gb) else f"{gb} GB"


def fmt_price(price_str: str, currency: str = "€") -> str:
    try:
        return f"{currency}{float(price_str):.2f}/mo"
    except (ValueError, TypeError):
        return price_str


def price_key(price_str: str) -> float:
    try:
        return float(price_str)
    except (ValueError, TypeError):
        return 0.0


# ------------------------------------------------------------------
# Deploy env helpers
# ------------------------------------------------------------------

_DEPLOY_ENV = Path(".phoxtail/deploy/.env")


def read_deploy_env(key: str) -> str | None:
    """Read a single key from the local .phoxtail/deploy/.env file."""
    if not _DEPLOY_ENV.exists():
        return None
    for line in _DEPLOY_ENV.read_text().splitlines():
        line = line.strip()
        if line.startswith(f"{key}="):
            return line[len(key) + 1 :].strip()
    return None


_SERVER_SENTINEL = "~/.phoxtail-project"


def verify_server_identity(
    user: str,
    ip: str,
    *,
    write_sentinel: bool = False,
    console: Console | None = None,
) -> None:
    """Abort if the target server doesn't match this project's recorded identity.

    Guard 1 (local): reads SERVER_IP from .phoxtail/deploy/.env — fails if
    absent or mismatched (requires no SSH).
    Guard 2 (server): reads ~/.phoxtail-project on the remote — fails if the
    sentinel records a different project slug. Writes the sentinel on first
    deploy when write_sentinel=True.
    """
    _con = console or Console()

    # Guard 1 — local pre-flight (no SSH needed)
    if _DEPLOY_ENV.exists():
        recorded_ip = read_deploy_env("SERVER_IP")
        if recorded_ip is None:
            _con.print(
                "[red]Error:[/red] SERVER_IP is missing from .phoxtail/deploy/.env\n"
                f"  Add [bold]SERVER_IP={ip}[/bold] to that file and re-run."
            )
            raise typer.Exit(1)
        if recorded_ip != ip:
            _con.print(
                f"[red]IP mismatch:[/red] This project is configured for "
                f"[bold]{recorded_ip}[/bold] but you passed [bold]{ip}[/bold].\n"
                "  Check the IP or delete .phoxtail/deploy/.env to reconfigure for a new server."
            )
            raise typer.Exit(1)

    # Guard 2 — server-side sentinel (keyed on project slug, not IP)
    local_slug = slugify(get_project_name())
    result = ssh_run(user, ip, f"cat {_SERVER_SENTINEL} 2>/dev/null")
    sentinel_slug = result.stdout.strip()

    if sentinel_slug and sentinel_slug != local_slug:
        _con.print(
            f"[red]Server identity mismatch:[/red] Server at [bold]{ip}[/bold] "
            f"belongs to project [bold]{sentinel_slug}[/bold], "
            f"not [bold]{local_slug}[/bold].\n"
            "  You may be targeting the wrong server."
        )
        raise typer.Exit(1)

    if write_sentinel and not sentinel_slug:
        ssh_run(user, ip, f"printf '%s' {local_slug} > {_SERVER_SENTINEL}")


# ------------------------------------------------------------------
# SSH helpers
# ------------------------------------------------------------------

_SSH_BASE = ["-o", "StrictHostKeyChecking=accept-new"]
_SSH_BATCH = [
    *_SSH_BASE,
    "-o",
    "ConnectTimeout=5",
    "-o",
    "BatchMode=yes",
]
# ControlMaster keeps one TCP connection open; subsequent SSH
# commands multiplex over it — fast and avoids re-authentication.
_SSH_MUX = [
    *_SSH_BASE,
    "-o",
    "ConnectTimeout=10",
    "-o",
    "ControlMaster=auto",
    "-o",
    "ControlPath=/tmp/phoxtail-ssh-%r@%h",
    "-o",
    "ControlPersist=300",
]

CLOUD_INIT_SENTINEL = "/var/lib/cloud/instance/boot-finished"


def _wait_for_ssh(
    user: str,
    ip: str,
    *,
    timeout: int = 120,
    interval: int = 5,
) -> tuple[bool, str]:
    """Block until SSH accepts a connection for *user*@*ip*.

    Returns (ok, reason). The reason carries SSH's own last words: a refused
    host key and a server that is merely slow both look like waiting from
    here, and reporting the first as a timeout sends the reader hunting in
    the wrong place.
    """
    cmd = [
        "ssh",
        *_SSH_BATCH,
        f"{user}@{ip}",
        "true",
    ]
    deadline = time.monotonic() + timeout
    stderr = ""
    while time.monotonic() < deadline:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            return True, ""
        stderr = result.stderr.strip()
        time.sleep(interval)
    reason = f"Gave up waiting for SSH after {timeout}s."
    if stderr:
        reason = f"{reason}\n\n{stderr}"
    return False, reason


def forget_host_key(ip: str) -> None:
    """Drop any known_hosts entry for *ip*.

    Only safe for a server that was just created: providers recycle IP
    addresses, so a leftover key belongs to a machine that no longer answers
    there, and SSH refuses the connection outright rather than accepting the
    new one. On an existing server a changed key is a real warning and must
    not be cleared.
    """
    subprocess.run(
        ["ssh-keygen", "-R", ip],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def cloud_init_report(
    user: str,
    ip: str,
    *,
    settle: int = 30,
) -> tuple[bool, str]:
    """Ask cloud-init how the bootstrap actually went.

    Keys on the reported status word, not the exit code: cloud-init exits
    non-zero for ``degraded`` as well as ``error``, and a warning a provider
    logs on every boot is enough to make degraded the norm. Judging by exit
    code would fail healthy servers.

    Only ``done`` counts as success. The sentinel file can land a moment
    before the status settles, so a ``running`` status is re-polled for
    *settle* seconds rather than being taken either way.
    """
    detail = ""
    deadline = time.monotonic() + settle
    while True:
        result = subprocess.run(
            ["ssh", *_SSH_BATCH, f"{user}@{ip}", "sudo cloud-init status --long"],
            capture_output=True,
            text=True,
        )
        detail = (result.stdout + result.stderr).strip()
        status = ""
        for line in result.stdout.splitlines():
            if line.startswith("status:"):
                status = line.split(":", 1)[1].strip()
                break
        if status != "running" or time.monotonic() >= deadline:
            break
        time.sleep(3)

    if status == "done":
        return True, detail
    # error, running, disabled, "not run", or unreadable — the detail says which.
    return False, detail or "Could not read cloud-init status."


def wait_for_cloud_init(
    user: str,
    ip: str,
    *,
    timeout: int = 600,
) -> tuple[bool, str]:
    """Wait for cloud-init, streaming its log output live.

    1. Poll until SSH is reachable (deploy user may not exist yet).
    2. If cloud-init already finished, report what it says.
    3. Otherwise tail the cloud-init log live until the sentinel appears.

    Returns (ok, detail). The sentinel file only means cloud-init *stopped* —
    it is written even when the commands inside failed — so finishing is
    always followed by asking cloud-init for its verdict.
    """
    reachable, reason = _wait_for_ssh(user, ip)
    if not reachable:
        return False, reason

    # Already done?
    check = subprocess.run(
        ["ssh", *_SSH_BATCH, f"{user}@{ip}", f"test -f {CLOUD_INIT_SENTINEL}"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if check.returncode == 0:
        return cloud_init_report(user, ip)

    # Tail the log live; exit as soon as the sentinel file appears.
    tail_cmd = (
        f"sudo tail -n 50 -f /var/log/cloud-init-output.log &"
        f" TAIL_PID=$!;"
        f" while [ ! -f {CLOUD_INIT_SENTINEL} ]; do sleep 3; done;"
        f" sleep 1; kill $TAIL_PID 2>/dev/null"
    )
    rc = subprocess.run(
        ["ssh", *_SSH_MUX, f"{user}@{ip}", tail_cmd],
        timeout=timeout,
    ).returncode

    # Close the ControlMaster so the next SSH command (e.g. deploy) opens a
    # fresh session with updated group memberships (docker, etc.) applied by
    # cloud-init's runcmd — those only take effect on new logins.
    subprocess.run(
        ["ssh", "-O", "exit", "-o", "ControlPath=/tmp/phoxtail-ssh-%r@%h", f"{user}@{ip}"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    if rc != 0:
        return False, "Timed out waiting for cloud-init to finish."

    return cloud_init_report(user, ip)


_SCP_OPTS = [
    "-o",
    "StrictHostKeyChecking=accept-new",
    "-o",
    "ControlMaster=auto",
    "-o",
    "ControlPath=/tmp/phoxtail-ssh-%r@%h",
    "-o",
    "ControlPersist=300",
]


def scp_to(user: str, ip: str, local: Path, remote: str) -> bool:
    """Copy a local file to the server. Returns True on success."""
    return (
        subprocess.run(
            ["scp", *_SCP_OPTS, str(local), f"{user}@{ip}:{remote}"],
            capture_output=True,
            text=True,
        ).returncode
        == 0
    )


def ssh_run(
    user: str,
    ip: str,
    command: str,
) -> subprocess.CompletedProcess[str]:
    """Run a command on the server, capture output."""
    return subprocess.run(
        ["ssh", *_SSH_MUX, f"{user}@{ip}", command],
        capture_output=True,
        text=True,
    )


def ssh_check(
    user: str,
    ip: str,
    command: str,
) -> bool:
    """Return True if a remote command exits 0."""
    return ssh_run(user, ip, command).returncode == 0


def ssh_live(
    user: str,
    ip: str,
    command: str,
    *,
    tty: bool = False,
) -> int:
    """Run with live output. tty=True for interactive."""
    cmd = ["ssh"]
    if tty:
        cmd.append("-t")
    cmd.extend([*_SSH_MUX, f"{user}@{ip}", command])
    return subprocess.run(cmd).returncode


# ------------------------------------------------------------------
# Git helpers
# ------------------------------------------------------------------


def detect_repo_url() -> str | None:
    """Auto-detect from local git origin remote."""
    result = subprocess.run(
        ["git", "remote", "get-url", "origin"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def to_ssh_url(url: str) -> str:
    """Convert HTTPS GitHub/GitLab URL to SSH format."""
    for host in ("github.com", "gitlab.com"):
        prefix = f"https://{host}/"
        if url.startswith(prefix):
            path = url.removeprefix(prefix)
            if not path.endswith(".git"):
                path += ".git"
            return f"git@{host}:{path}"
    return url


def git_host(url: str) -> str:
    """Extract host from git@host:path URL."""
    if "@" in url and ":" in url:
        return url.split("@", 1)[1].split(":", 1)[0]
    return "github.com"


# ------------------------------------------------------------------
# Cloud-init
# ------------------------------------------------------------------


def render_bootstrap(deploy_user: str, ssh_keys: list[SSHKey]) -> str:
    """Render the cloud-init bootstrap template."""
    public_keys = [k.public_key for k in ssh_keys if k.public_key]
    return render_template(
        "cloud_init/bootstrap.yml.j2",
        {
            "deploy_user": deploy_user,
            "ssh_public_keys": public_keys,
        },
    )
