"""The CMS app's HTTP face.

Found because ``PhoxtailCmsConfig`` subclasses ``PhoxtailAppConfig``.
Declaring ``versions`` is the whole contract, and each key becomes a path
segment under ``/api/cms/``.
"""

from __future__ import annotations

from phoxtail.cms.api.v1 import router as v1

versions = {"v1": v1}
