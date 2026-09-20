"""Starting the CLI must not load what only one command needs.

Every shell completion and every ``--help`` pays the import cost of
``phoxtail.__main__``. Heavy libraries — the MCP stack, HTTP clients,
interactive prompts — belong inside the command that uses them.
"""

import subprocess
import sys

HEAVY = ("fastmcp", "mcp", "httpx", "questionary", "django")


def test_cli_starts_without_heavy_imports():
    # A fresh interpreter: the test process itself has long since imported everything.
    code = (
        "import sys, phoxtail.__main__; "
        "assert 'phoxtail.cli.net' in sys.modules, 'the CLI did not load'; "
        f"print(sorted(m for m in {HEAVY!r} if m in sys.modules))"
    )
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    assert out.stdout.strip() == "[]", f"loaded at startup: {out.stdout.strip()}"
