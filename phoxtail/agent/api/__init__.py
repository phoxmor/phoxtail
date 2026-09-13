"""The agent app's HTTP face.

Found because ``PhoxtailAgentConfig`` subclasses ``PhoxtailAppConfig``.
Declaring ``versions`` is the whole contract, and each key becomes a path
segment under ``/api/agent/``.
"""

from __future__ import annotations

from phoxtail.agent.api.v1 import router as v1

versions = {"v1": v1}
