"""Every agent surface must import without the chatbot's optional dependency.

``phoxtail.agent`` is installed in every project; ``pydantic_ai`` arrives only
with the ``chatbot`` extra. Both surfaces are imported at startup — the API by
the router mount, the MCP tools by discovery — so a single module-level
``import pydantic_ai`` anywhere under ``api/`` or ``mcp/`` would stop a project
without the extra from starting at all.

Nothing in the running process can notice that: every environment these tests
run in has the extra installed. So the absence is staged, in a subprocess that
boots Django from scratch with the package hidden from the import system.

A subprocess rather than ``monkeypatch``, because an honest check has to import
``llm``, ``chat_blocks``, ``tools`` and ``models`` freshly — a module already in
``sys.modules`` is handed back without being re-executed, so a bad import added
to one of them would pass unnoticed. Clearing them in-process instead would
re-register the agent's models on a live app registry.

The deferred imports inside those four modules are deliberate. This is the test
that says so.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap

_HIDDEN = "pydantic_ai"

_CHECK = textwrap.dedent(f'''
    import importlib, importlib.util, pkgutil, sys

    class Absent:
        """Refuse one package, the way an uninstalled one is refused."""
        def find_spec(self, name, path=None, target=None):
            if name == "{_HIDDEN}" or name.startswith("{_HIDDEN}."):
                raise ModuleNotFoundError(f"No module named {{name!r}}", name=name)
            return None

    sys.meta_path.insert(0, Absent())
    # find_spec is patched separately: the finder raises, where a genuinely
    # missing package simply answers None, and that is what apps.py would see.
    real = importlib.util.find_spec
    importlib.util.find_spec = (
        lambda name, package=None: None if name.startswith("{_HIDDEN}") else real(name, package)
    )
    assert importlib.util.find_spec("{_HIDDEN}") is None

    import django
    django.setup()

    import phoxtail.agent.api as api_package
    import phoxtail.agent.mcp as mcp_package

    for package in (api_package, mcp_package):
        for info in pkgutil.walk_packages(package.__path__, f"{{package.__name__}}."):
            if ".tests" in info.name:
                continue
            importlib.import_module(info.name)

    assert "{_HIDDEN}" not in sys.modules, "something imported it after all"
    print("OK")
''')


def test_the_agent_surface_imports_without_the_chatbot_extra():
    """Boot Django and import both surfaces with the package unreachable."""
    result = subprocess.run(
        [sys.executable, "-c", _CHECK],
        capture_output=True,
        text=True,
        env={
            "PATH": "/usr/bin:/bin",
            "DJANGO_SETTINGS_MODULE": "phoxtail.core.tests.settings",
            "PYTHONPATH": ":".join(sys.path),
        },
    )
    assert result.returncode == 0, result.stderr
    assert "OK" in result.stdout
