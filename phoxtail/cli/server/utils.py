"""Shared helpers for server commands — SSH, git, cloud-init, formatting."""

import subprocess
import time
from pathlib import Path

from phoxtail.cli.server.providers.base import SSHKey
from phoxtail.cli.utils.templates import render_template

# ------------------------------------------------------------------
# Formatting helpers
# ------------------------------------------------------------------


def fmt_memory(gb: float) -> str:
    return f"{int(gb)} GB" if gb == int(gb) else f"{gb} GB"


def fmt_price(price_str: str) -> str:
    try:
        return f"€{float(price_str):.2f}/mo"
    except (ValueError, TypeError):
        return price_str


def price_key(price_str: str) -> float:
    try:
        return float(price_str)
    except (ValueError, TypeError):
        return 0.0


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
) -> bool:
    """Block until SSH accepts a connection for *user*@*ip*."""
    cmd = [
        "ssh",
        *_SSH_BATCH,
        f"{user}@{ip}",
        "true",
    ]
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = subprocess.run(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if result.returncode == 0:
            return True
        time.sleep(interval)
    return False


def wait_for_cloud_init(
    user: str,
    ip: str,
    *,
    timeout: int = 600,
) -> bool:
    """Wait for cloud-init, streaming its log output live.

    1. Poll until SSH is reachable (deploy user may not exist yet).
    2. If cloud-init already finished, return immediately.
    3. Otherwise tail the cloud-init log live until the sentinel appears.
    """
    if not _wait_for_ssh(user, ip):
        return False

    # Already done?
    check = subprocess.run(
        ["ssh", *_SSH_BATCH, f"{user}@{ip}", f"test -f {CLOUD_INIT_SENTINEL}"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if check.returncode == 0:
        return True

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

    return rc == 0


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
