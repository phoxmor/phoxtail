"""Where a dependency comes from, and how to write that into pyproject.toml.

`phoxtail hatch` and `phoxtail install` both have to answer the same question:
the user named a package, but should uv resolve it from PyPI, from a git
repository, or from a checkout on this machine? The locator syntax here is
uv's own — `git+ssh://…@ref`, a path, a wheel URL — so that anyone who has
used `uv add` or `pip install` already knows it.

PyPI is the default and needs no locator; every other kind becomes a
`[tool.uv.sources]` entry alongside the ordinary dependency declaration.
"""

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

import httpx

from phoxtail.cli.utils.packages import is_declared

PYPI = "pypi"
GIT = "git"
PATH = "path"
URL = "url"

# Archive extensions uv can install directly, local or over https.
_ARCHIVE_SUFFIXES = (".whl", ".tar.gz", ".zip")
# git's own wording when the machine, not the repository, is the problem.
_OFFLINE_HINTS = (
    "could not resolve host",
    "could not resolve hostname",
    "temporary failure in name resolution",
    "network is unreachable",
    "connection timed out",
    "connection refused",
)
# scp-style git remote, e.g. git@github.com:<org>/<package>.git
_SCP_RE = re.compile(r"^[\w.+-]+@[\w.-]+:[^/].*$")


class InvalidSource(Exception):
    """The --source value is not a locator uv can resolve."""


class NoInsertionPoint(Exception):
    """pyproject.toml has no [project] dependencies array to append to."""


@dataclass(frozen=True)
class Source:
    """A resolved answer to "where does this package come from?"."""

    kind: str = PYPI
    location: str = ""
    # Branch, tag or commit for a git source. uv records all three under
    # `rev`, so there is only ever the one key to write.
    ref: str | None = None

    @property
    def is_pypi(self) -> bool:
        return self.kind == PYPI

    def entry_value(self) -> str | None:
        """The inline TOML table for [tool.uv.sources], or None for PyPI."""
        if self.kind == PYPI:
            return None
        if self.kind == GIT:
            ref = f', rev = "{self.ref}"' if self.ref else ""
            return f'{{ git = "{self.location}"{ref} }}'
        if self.kind == URL:
            return f'{{ url = "{self.location}" }}'
        # A directory is a checkout to develop against; an archive is a fixed
        # build, and marking that editable is an error rather than a nicety.
        if Path(self.location).is_dir():
            return f'{{ path = "{self.location}", editable = true }}'
        return f'{{ path = "{self.location}" }}'

    def describe(self) -> str:
        if self.kind == PYPI:
            return "PyPI"
        if self.kind == GIT:
            return f"{self.location}@{self.ref}" if self.ref else self.location
        return self.location


def _split_git_ref(url: str) -> tuple[str, str | None]:
    """Split a trailing `@ref` off a git URL.

    The `@` in `git@github.com` is part of the host, not a ref, so only an
    `@` after the last `/` counts.
    """
    at = url.rfind("@")
    if at > url.rfind("/"):
        return url[:at], url[at + 1 :]
    return url, None


def parse_source(spec: str | None) -> Source:
    """Turn a --source value into a Source. Empty or "pypi" means the index."""
    if spec is None or not spec.strip() or spec.strip().lower() == PYPI:
        return Source()
    spec = spec.strip()

    if spec.startswith("git+"):
        location, ref = _split_git_ref(spec[len("git+") :])
        return Source(kind=GIT, location=location, ref=ref)
    # Bare git remotes, as copied out of `git remote -v`.
    if spec.startswith("ssh://") or _SCP_RE.match(spec) or spec.endswith(".git"):
        location, ref = _split_git_ref(spec)
        return Source(kind=GIT, location=location, ref=ref)

    if spec.startswith(("http://", "https://")):
        if spec.endswith(_ARCHIVE_SUFFIXES):
            return Source(kind=URL, location=spec)
        raise InvalidSource(
            f"'{spec}' points at neither an archive nor a repository.\n"
            "For a git repository prefix it with [cyan]git+[/cyan]; for a "
            "wheel or sdist give the full file URL."
        )

    # Anything else is a path. Absolute, because the generated pyproject.toml
    # is read from the new project's directory, not from where hatch ran.
    path = Path(spec).expanduser()
    if not path.exists():
        raise InvalidSource(f"'{spec}' is not a git URL, an archive URL, or an existing path.")
    return Source(kind=PATH, location=str(path.resolve()))


def package_name(source: Source) -> str | None:
    """The distribution name implied by a source, when one can be read off it.

    Only git URLs carry a usable name: a checkout directory may be named
    anything, and an archive filename is a build artefact, not a promise.
    """
    if source.kind != GIT:
        return None
    name = source.location.rstrip("/").split("/")[-1]
    if name.endswith(".git"):
        name = name[:-4]
    return name or None


def pypi_releases(package: str) -> list[str] | None:
    """Versions of `package` released on PyPI.

    An empty list means PyPI answered and has no such project; None means it
    could not answer at all, which is not the same thing — an unreachable
    index must never be reported to the user as a missing package.

    Asked over the JSON API rather than uv: `uv pip index` is gone as of uv
    0.11, and no other uv subcommand lists the versions of a package that is
    not installed.
    """
    try:
        response = httpx.get(f"https://pypi.org/pypi/{package}/json", timeout=10.0, follow_redirects=True)
    except httpx.HTTPError:
        return None
    if response.status_code == 404:
        return []
    if response.status_code != 200:
        return None
    try:
        return sorted(response.json().get("releases", {}))
    except ValueError:
        return None


def preflight(source: Source, package: str) -> tuple[bool | None, str]:
    """Check the source can be reached before anything is written.

    True is a source that answered, False one that answered "no such
    package", and None one that could not be asked at all — offline, or an
    index that never replied. Callers must not treat None as False: uv
    resolves from its own cache happily enough without a network, and a
    check that cannot run is no reason to stop a command that could work.
    """
    if source.kind == PYPI:
        releases = pypi_releases(package)
        if releases is None:
            return None, "PyPI could not be reached."
        if not releases:
            return False, (
                f"[bold]{package}[/bold] was not found on PyPI.\n"
                "If it lives somewhere else, name that source:\n"
                f"  [cyan]phoxtail install --source git+ssh://git@github.com/your-org/{package}.git[/cyan]"
            )
        return True, ""

    if source.kind == GIT:
        try:
            result = subprocess.run(
                ["git", "ls-remote", source.location, "HEAD"],
                capture_output=True,
                text=True,
                timeout=30,
            )
        except subprocess.TimeoutExpired:
            # Most often git sitting on a host-key or credential prompt that
            # nothing here can answer — but it may equally be a dead link.
            return None, f"[bold]{source.location}[/bold] did not answer within 30s."
        if result.returncode != 0:
            stderr_lower = result.stderr.lower()
            if "permission denied" in stderr_lower or "publickey" in stderr_lower:
                return False, (
                    f"SSH access denied for [bold]{package}[/bold].\n"
                    "You don't have access to this repository — contact [cyan]hello@phoxmor.com[/cyan]."
                )
            if any(hint in stderr_lower for hint in _OFFLINE_HINTS):
                return None, f"Could not reach [bold]{source.location}[/bold]: no network."
            return False, f"Could not reach [bold]{source.location}[/bold].\nError: {result.stderr.strip()}"
        return True, ""

    if source.kind == PATH and not Path(source.location).exists():
        return False, f"[bold]{source.location}[/bold] does not exist."

    return True, ""


def add_dependency(content: str, package: str) -> str:
    """Append `package` to [project].dependencies, or return `content` if already declared.

    Raises NoInsertionPoint when the array cannot be found — returning the
    text unchanged would let every later step report success for a package
    that was never declared.
    """
    # A pinned entry ("wagtail>=7.4.2,<8.0") declares the package just as much
    # as a bare one does — appending a second entry for it would leave the
    # project with two conflicting requirements for one distribution.
    # runtime_only: a dev-group or extras entry never reaches the production
    # image, so it must not block declaring the package as a runtime dependency.
    if is_declared(content, package, runtime_only=True):
        return content
    # Anchored inside the [project] table: keying off what follows the array
    # instead landed every install in dependency-groups.dev, which the
    # production image drops with `uv sync --no-dev`.
    header = re.search(r"(?m)^\[project\][ \t]*$", content)
    if header is None:
        raise NoInsertionPoint("no [project] table")
    tail = content[header.end() :]
    next_table = re.search(r"(?m)^\[", tail)
    table = tail[: next_table.start()] if next_table else tail
    array = re.search(r"(?ms)^dependencies\s*=\s*\[\n.*?^\]", table)
    if array is not None:
        closing_bracket = header.end() + array.end() - 1
        return content[:closing_bracket] + f'    "{package}",\n' + content[closing_bracket:]
    # `dependencies = []` and single-line arrays are valid TOML too.
    inline = re.search(r"(?m)^dependencies\s*=\s*\[(?P<inner>[^\[\]]*)\]", table)
    if inline is None:
        raise NoInsertionPoint("no dependencies array under [project]")
    inner = inline.group("inner").strip().rstrip(",")
    new_inner = f'{inner}, "{package}"' if inner else f'"{package}"'
    start, end = header.end() + inline.start("inner"), header.end() + inline.end("inner")
    return content[:start] + new_inner + content[end:]


def add_source(content: str, package: str, source: Source) -> str:
    """Point `package` at `source` in [tool.uv.sources]. PyPI writes nothing."""
    value = source.entry_value()
    if value is None:
        return content
    # Keyed on the package, not the URL: the same URL under another package's
    # key must not stop this one from getting a source, and a second entry for
    # an already-sourced package would be a duplicate TOML key.
    if re.search(rf"(?m)^{re.escape(package)}\s*=\s*{{", content):
        return content
    source_line = f"{package} = {value}"
    header = re.search(r"(?m)^\[tool\.uv\.sources\][ \t]*$", content)
    if header:
        # Right under the table header — appended to the end of the file, the
        # key would belong to whichever table happens to come last.
        return content[: header.end()] + f"\n{source_line}" + content[header.end() :]
    # The hatched template has [tool.uv] but no [tool.uv.sources]; dropping the
    # source silently would send `uv lock` to PyPI for a private package.
    return content.rstrip() + f"\n\n[tool.uv.sources]\n{source_line}\n"
