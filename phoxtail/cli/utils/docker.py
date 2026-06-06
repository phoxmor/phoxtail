"""Docker command utilities."""

import os
import subprocess
import zipfile
from pathlib import Path

import yaml
from jinja2 import Environment


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
    result = subprocess.run(cmd, capture_output=capture, text=True, env=docker_env(), input=stdin_data)
    if result.returncode != 0 and capture:
        stderr = result.stderr.strip() if result.stderr else ""
        raise subprocess.CalledProcessError(result.returncode, cmd, output=result.stdout, stderr=stderr)
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
        raise subprocess.CalledProcessError(result.returncode, cmd, output=result.stdout, stderr=stderr)
    return result


def collect_package_compose_fragments(context: dict) -> dict:
    """Scan installed packages for app compose fragments and return merged services+volumes.

    Convention: any package (excluding phoxtail itself) that contains
    ``{top_package}/deploy/compose.yaml.j2`` contributes a fragment.
    Fragments are rendered with the same Jinja2 context as the base template
    and must declare only ``services:`` and/or ``volumes:`` keys.

    Scans .venv/lib/python*/site-packages/ when a .venv is present (requires
    ``uv sync`` to have been run first). Falls back to scanning wheels/ for
    backwards compatibility.
    """
    merged: dict = {"services": {}, "volumes": {}}
    jinja_env = Environment()

    venv_dir = Path(".venv")
    if venv_dir.exists():
        for site_packages in sorted(venv_dir.glob("lib/python*/site-packages")):
            for fragment_path in sorted(site_packages.glob("*/deploy/compose.yaml.j2")):
                top_package = fragment_path.parent.parent.name
                if top_package == "phoxtail":
                    continue
                template_str = fragment_path.read_text()
                rendered = jinja_env.from_string(template_str).render(**context)
                fragment = yaml.safe_load(rendered) or {}
                merged["services"].update(fragment.get("services", {}))
                merged["volumes"].update(fragment.get("volumes", {}))
        return merged

    # Fallback: scan wheels/ directory
    wheels_dir = Path("wheels")
    if not wheels_dir.exists():
        return merged

    for wheel_path in sorted(wheels_dir.glob("*.whl")):
        if wheel_path.name.startswith("phoxtail-"):
            continue
        with zipfile.ZipFile(wheel_path) as zf:
            candidates = [name for name in zf.namelist() if name.endswith("/deploy/compose.yaml.j2")]
            for fragment_name in candidates:
                template_str = zf.read(fragment_name).decode("utf-8")
                rendered = jinja_env.from_string(template_str).render(**context)
                fragment = yaml.safe_load(rendered) or {}
                merged["services"].update(fragment.get("services", {}))
                merged["volumes"].update(fragment.get("volumes", {}))

    return merged
