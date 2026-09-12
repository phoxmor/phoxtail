"""The core app's HTTP face.

Found because ``PhoxtailCoreConfig`` subclasses ``PhoxtailAppConfig``.
Declaring ``versions`` is the whole contract, and each key becomes a path
segment under ``/api/core/``.
"""

from __future__ import annotations

from phoxtail.core.api.v1 import router as v1

versions = {"v1": v1}
