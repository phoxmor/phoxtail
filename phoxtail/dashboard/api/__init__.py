"""The dashboard's HTTP face.

Found because ``PhoxtailDashboardConfig`` subclasses ``PhoxtailAppConfig``.
Nothing registers this module: declaring ``versions`` is the whole contract,
and each key becomes a path segment under ``/api/dashboard/``.
"""

from __future__ import annotations

from phoxtail.dashboard.api.v1 import router as v1

versions = {"v1": v1}
