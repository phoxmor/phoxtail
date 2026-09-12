"""The media app's HTTP face.

Found because ``PhoxtailMediaConfig`` subclasses ``PhoxtailAppConfig``.
Declaring ``versions`` is the whole contract, and each key becomes a path
segment under ``/api/media/``.
"""

from __future__ import annotations

from phoxtail.media.api.v1 import router as v1

versions = {"v1": v1}
