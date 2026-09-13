"""The CMS app's HTTP face.

Found because ``PhoxtailCmsConfig`` subclasses ``PhoxtailAppConfig``.
Declaring ``versions`` is the routing contract, and each key becomes a path
segment under ``/api/cms/``.
"""

from __future__ import annotations

from phoxtail.cms.api.v1 import router as v1
from phoxtail.cms.api.v1.page_schemas import contribute_site_page

versions = {"v1": v1}

page_schemas = [contribute_site_page]
