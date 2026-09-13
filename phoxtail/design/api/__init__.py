"""The design system's HTTP face.

Found because ``PhoxtailDesignConfig`` subclasses ``PhoxtailAppConfig``.
Declaring ``versions`` is the routing contract, and each key becomes a path
segment under ``/api/design/``.
"""

from __future__ import annotations

from phoxtail.design.api.v1 import router as v1

versions = {"v1": v1}
