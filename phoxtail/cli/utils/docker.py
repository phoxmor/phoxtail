"""Docker command utilities."""

import os
import subprocess


def docker_env() -> dict[str, str]:
    """Return os.environ with HOST_UID/HOST_GID set.

    Docker Compose interpolates these into the ``user:`` directive so
    that containers create files owned by the host user, not root.
    """
    env = os.environ.copy()
    env.setdefault("HOST_UID", str(os.getuid()))
    env.setdefault("HOST_GID", str(os.getgid()))
    return env


def docker_manage(
    *args: str,
    capture: bool = True,
    stdin_data: str | None = None,
) -> subprocess.CompletedProcess:
    """Run a Django management command inside the web container."""
    cmd = ["docker", "compose", "run", "--rm", "web", "python", "manage.py", *args]
    result = subprocess.run(
        cmd, capture_output=capture, text=True, env=docker_env(), input=stdin_data
    )
    if result.returncode != 0 and capture:
        stderr = result.stderr.strip() if result.stderr else ""
        raise subprocess.CalledProcessError(
            result.returncode, cmd, output=result.stdout, stderr=stderr
        )
    return result


def docker_db(*args: str) -> subprocess.CompletedProcess:
    """Run a command inside the db container."""
    cmd = [
        "docker",
        "compose",
        "exec",
        "db",
        "sh",
        "-c",
        " ".join(args),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, env=docker_env())
    if result.returncode != 0:
        stderr = result.stderr.strip() if result.stderr else ""
        raise subprocess.CalledProcessError(
            result.returncode, cmd, output=result.stdout, stderr=stderr
        )
    return result
