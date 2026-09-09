"""No router may authenticate with a backend that resolves a bare User.

Every endpoint in phoxtail reads ``request.auth`` as an
:class:`~phoxtail.core.authorization.AuthorizationContext`. Ninja's stock
session backends — ``SessionAuth`` and the ``django_auth`` instance of it
— resolve a ``User`` instead, so a router wired to one of them raises
``AttributeError: 'User' object has no attribute 'user'`` on its first
authenticated request.

That failure is invisible until runtime: it type-checks, imports, and
passes every test that does not exercise the endpoint. It shipped exactly
once, on the chatbot's SSE router, which no test covered.

Scanning the source is the honest check here. The alternative — walking
the mounted router tree — cannot see it, because ninja resolves
inherited auth lazily and a router's own ``auth=`` is not visible on its
operations until a request arrives.
"""

from __future__ import annotations

import pathlib
import re

PACKAGE_ROOT = pathlib.Path(__file__).resolve().parents[2]

# Where ninja's stock backend is legitimately named: the wrapper that
# exists precisely to adapt it, and this test.
_ALLOWED = {
    PACKAGE_ROOT / "api" / "auth.py",
    pathlib.Path(__file__).resolve(),
}

# Narrow on purpose: "django_auth" is an ordinary identifier that unrelated
# code may legitimately use as a local name. Only ninja's own backend counts.
_NINJA_IMPORT = re.compile(r"from\s+ninja\.security\s+import\b.*\b(SessionAuth|django_auth)\b")
_NINJA_USE = re.compile(r"(?<!Phoxtail)\bSessionAuth\s*\(|\bauth\s*=\s*django_auth\b")


def _offenders() -> list[str]:
    hits = []
    for path in PACKAGE_ROOT.rglob("*.py"):
        if path.resolve() in _ALLOWED:
            continue
        for lineno, line in enumerate(path.read_text().splitlines(), 1):
            if line.lstrip().startswith("#"):
                continue
            if _NINJA_IMPORT.search(line) or _NINJA_USE.search(line):
                hits.append(f"{path.relative_to(PACKAGE_ROOT)}:{lineno}: {line.strip()}")
    return hits


def test_no_router_uses_ninjas_stock_session_backend():
    offenders = _offenders()
    assert not offenders, (
        "These resolve a bare User where phoxtail expects an "
        "AuthorizationContext. Use PhoxtailSessionAuth from "
        "phoxtail.api.auth instead:\n  " + "\n  ".join(offenders)
    )
