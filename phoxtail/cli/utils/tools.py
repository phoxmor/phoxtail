"""The programs the CLI runs on the host, and what to say when one cannot run.

Commands shell out to docker, uv, git, ssh, scp, ssh-keygen and rsync. When
one of those is not installed, ``subprocess`` raises ``FileNotFoundError``,
which reached the user as a traceback — often after the command had already
changed something. So a command asks here first, before its first side
effect, and a missing program reads as what it is, with what to do about it.

Two layers, because callers need two things:

- :func:`check` only answers: the first :class:`Problem` found, or None.
  A flow that can carry on without a program (hatch skipping its Docker
  steps) asks this.
- :func:`require` answers by printing the problem and exiting. A command
  that cannot do anything without the program asks this.

Lookups use ``shutil.which`` against the same ``PATH`` the command will run
with, rather than catching ``FileNotFoundError`` afterwards: by the time the
exception is raised, the command may already be halfway through its work.
"""

import shutil
import subprocess
import sys
from dataclasses import dataclass
from typing import NoReturn

import typer
from rich.console import Console
from rich.markup import escape

console = Console()

DOCKER = "docker"
# Compose v2 is a docker plugin, not a program of its own: the old
# standalone `docker-compose` does not provide `docker compose`.
COMPOSE = "docker compose"
UV = "uv"
GIT = "git"
SSH = "ssh"
SCP = "scp"
SSH_KEYGEN = "ssh-keygen"
RSYNC = "rsync"

_OPENSSH = "Install the OpenSSH client, which provides ssh, scp and ssh-keygen."

_INSTALL = {
    DOCKER: "Install Docker: https://docs.docker.com/get-started/get-docker/",
    COMPOSE: (
        "Install the Docker Compose plugin (Compose v2), which provides `docker compose`:\n"
        "https://docs.docker.com/compose/install/"
    ),
    UV: "Install uv: curl -LsSf https://astral.sh/uv/install.sh | sh\nor: pip install uv",
    GIT: "Install git: https://git-scm.com/downloads",
    SSH: _OPENSSH,
    SCP: _OPENSSH,
    SSH_KEYGEN: _OPENSSH,
    RSYNC: "Install rsync from your system's package manager.",
}

_NAMES = {
    DOCKER: "Docker",
    COMPOSE: "Docker Compose",
}

# Docker Desktop can take a while to answer while it is still starting; a
# daemon that has not answered by then is reported, not waited on forever.
DAEMON_TIMEOUT = 20


@dataclass(frozen=True)
class Problem:
    """Why a program cannot run, and what to do about it."""

    reason: str
    remedy: str


def check(*programs: str, daemon: bool = False) -> Problem | None:
    """Return the first reason one of *programs* cannot run, or None.

    *programs* are this module's names (``DOCKER``, ``COMPOSE``, ``UV``…).
    ``daemon=True`` also asks the Docker daemon to answer, which catches a
    daemon that is stopped or that this user may not talk to. It costs a
    round-trip, so only flows that do slow or remote work before their first
    Docker call ask for it; a one-off command is better served by Docker's
    own "Cannot connect" message.
    """
    for program in programs:
        problem = _compose_problem() if program == COMPOSE else _missing(program)
        if problem is not None:
            return problem
    if daemon:
        return _missing(DOCKER) or _daemon_problem()
    return None


def require(*programs: str, daemon: bool = False, note: str | None = None) -> None:
    """Exit with the first reason one of *programs* cannot run.

    *note* is a line of the caller's own, such as a flag that avoids the
    program altogether.
    """
    problem = check(*programs, daemon=daemon)
    if problem is not None:
        fail(problem, note=note)


def fail(problem: Problem, *, note: str | None = None) -> NoReturn:
    """Print *problem* the way every command reports one, then exit."""
    console.print(f"[red]Error:[/red] {escape(problem.reason)}.")
    for line in problem.remedy.splitlines():
        console.print(f"  {escape(line)}")
    if note:
        console.print(f"  {note}")
    raise typer.Exit(1)


def compose_version() -> str | None:
    """The installed Compose v2 version, as `docker compose` reports it.

    None when there is no answer: docker missing, the Compose plugin
    missing, or a reply that names no version.
    """
    if shutil.which(DOCKER) is None:
        return None
    result = _ask_compose()
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def _ask_compose() -> subprocess.CompletedProcess[str]:
    return subprocess.run([DOCKER, "compose", "version", "--short"], capture_output=True, text=True)


def _missing(program: str) -> Problem | None:
    if shutil.which(program) is not None:
        return None
    name = _NAMES.get(program, program)
    return Problem(f"{name} not found", _INSTALL[program])


def _compose_problem() -> Problem | None:
    problem = _missing(DOCKER)
    if problem is not None:
        return problem
    result = _ask_compose()
    if result.returncode == 0 and result.stdout.strip():
        return None
    # Docker's words matter here too: a broken `docker context` fails every
    # docker command, and is not fixed by reinstalling the plugin.
    return Problem("Docker Compose v2 not found", _docker_said(result) + _INSTALL[COMPOSE])


def _daemon_problem() -> Problem | None:
    try:
        result = subprocess.run(
            [DOCKER, "info", "--format", "{{.ServerVersion}}"],
            capture_output=True,
            text=True,
            timeout=DAEMON_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        return Problem(
            "Docker did not answer",
            f"`docker info` gave no answer within {DAEMON_TIMEOUT}s — if Docker is still starting, "
            "wait for it and try again.",
        )
    # A daemon that answers names its version; an empty reply is no answer.
    if result.returncode == 0 and result.stdout.strip():
        return None
    # Docker's own last line says which it is — stopped, or permission
    # denied on its socket — better than a guess made here could.
    return Problem("Docker is not running, or this user may not use it", _docker_said(result) + _start_docker())


def _docker_said(result: subprocess.CompletedProcess[str]) -> str:
    """Docker's last line on a failed call, as a line of a remedy."""
    said = (result.stderr or result.stdout).strip().splitlines()
    return f"Docker said: {said[-1]}\n" if said else ""


def _start_docker() -> str:
    if sys.platform == "darwin":
        return "Start Docker Desktop, wait until it reports it is running, and try again."
    if sys.platform.startswith("linux"):
        return (
            "Start it: sudo systemctl start docker\n"
            "If it says permission denied, add yourself to the docker group:\n"
            "sudo usermod -aG docker $USER — then log out and back in."
        )
    return "Start Docker and try again."
