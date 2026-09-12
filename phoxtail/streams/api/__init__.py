"""The streams app's HTTP face.

Found because ``PhoxtailStreamsConfig`` subclasses ``PhoxtailAppConfig``.
Declaring ``versions`` is the whole contract, and each key becomes a path
segment under ``/api/streams/``.
"""

from __future__ import annotations

from phoxtail.streams.api.v1 import router as v1

versions = {"v1": v1}
