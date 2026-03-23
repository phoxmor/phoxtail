"""Docker command utilities."""

import subprocess


def docker_manage(*args: str, capture: bool = True) -> subprocess.CompletedProcess:
    """Run a Django management command inside the web container."""
    cmd = ["docker", "compose", "run", "--rm", "web", "python", "manage.py", *args]
    result = subprocess.run(cmd, capture_output=capture, text=True)
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
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        stderr = result.stderr.strip() if result.stderr else ""
        raise subprocess.CalledProcessError(
            result.returncode, cmd, output=result.stdout, stderr=stderr
        )
    return result
