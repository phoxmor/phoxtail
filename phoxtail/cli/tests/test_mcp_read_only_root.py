"""The MCP server works where the project root cannot be written.

A production image has no ``.phoxtail`` and its ``/app`` belongs to root while
the app runs as uid 1000, so nothing may require creating ``.phoxtail`` there:
not importing :mod:`phoxtail.mcp`, which the web process does to check token
scopes, and not the screenshot tools' saved copy.
"""

from __future__ import annotations

import os
import subprocess
import sys

import pytest

from phoxtail.streams.mcp.render import _save_screenshot

needs_permissions = pytest.mark.skipif(os.geteuid() == 0, reason="root writes through read-only permissions")


def test_screenshot_copy_is_saved_where_the_root_is_writable(project_dir):
    _save_screenshot("page-1", "desktop-light", b"png")

    assert (project_dir / ".phoxtail/vision/page-1-desktop-light.png").read_bytes() == b"png"


@needs_permissions
def test_screenshot_copy_is_skipped_where_the_root_is_read_only(project_dir):
    project_dir.chmod(0o555)
    try:
        _save_screenshot("page-1", "desktop-light", b"png")
    finally:
        project_dir.chmod(0o755)

    assert not (project_dir / ".phoxtail").exists()


def test_token_scopes_load_where_app_folder_cannot_be_written():
    # Every API token check expands its scopes through derive(), which loads
    # every app's MCP tools. A fresh interpreter, so module-level code runs
    # again without replacing the server the rest of the suite registered its
    # tools on; /app exists and refuses writes, as in a production image.
    script = (
        "import os, pathlib\n"
        "real_is_dir, real_mkdir = pathlib.Path.is_dir, pathlib.Path.mkdir\n"
        "def in_app(path):\n"
        "    return str(path) == '/app' or str(path).startswith('/app/')\n"
        "pathlib.Path.is_dir = lambda self: str(self) == '/app' or real_is_dir(self)\n"
        "def mkdir(self, *args, **kwargs):\n"
        "    if in_app(self):\n"
        "        raise PermissionError(13, 'Permission denied', str(self))\n"
        "    return real_mkdir(self, *args, **kwargs)\n"
        "pathlib.Path.mkdir = mkdir\n"
        "os.environ['DJANGO_SETTINGS_MODULE'] = 'phoxtail.core.tests.settings'\n"
        "import django\n"
        "django.setup()\n"
        "from phoxtail.tokens.bundles import derive\n"
        "assert derive()\n"
    )

    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)

    assert result.returncode == 0, result.stderr
