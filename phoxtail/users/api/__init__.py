"""The users app's HTTP face.

Found because ``PhoxtailUsersConfig`` subclasses ``PhoxtailAppConfig``.
Declaring ``versions`` is the routing contract, and each key becomes a path
segment under ``/api/users/``.
"""

from __future__ import annotations

from phoxtail.users.api.v1 import router as v1

versions = {"v1": v1}
