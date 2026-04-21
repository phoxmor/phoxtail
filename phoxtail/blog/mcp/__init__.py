"""MCP tools contributed by ``phoxtail.blog``.

Discovery happens through the ``phoxtail.mcp_modules`` Python
entry-point group (see ``pyproject.toml``), which is the standard
plugin mechanism in the Python ecosystem (pytest, sphinx, flake8 all
use it). Because the ``phoxtail`` distribution bundles many optional
Django apps into one wheel, the entry point fires whenever
``phoxtail`` is installed — even for consumers who did not enable blog
in their project. We therefore gate registration on the project
manifest (``phoxtail.toml → [project].apps``), the host-side source of
truth for "which phoxtail apps this project uses":

* blog listed in ``phoxtail.toml`` → submodules import, decorators
  register, ``phoxtail_blog_*`` tools appear in the MCP catalog.
* blog absent → this module is a no-op; the catalog stays clean and
  the agent never sees a tool whose endpoint 404s.

Note: we can't gate on ``django.apps.is_installed`` here — ``phoxtail
mcp serve`` runs on the host without a Django runtime (the server is a
pure HTTP client talking to the dockerized backend). ``phoxtail.toml``
is the analogous manifest on the host.

See ``phoxtail/docs/docs/mcp/pages-domain.md`` ("MCP registration") for
the full rationale.
"""

from __future__ import annotations

from phoxtail.cli.utils.config import get_project_apps

if "phoxtail.blog" in get_project_apps():
    from phoxtail.blog.mcp import authors  # noqa: F401
