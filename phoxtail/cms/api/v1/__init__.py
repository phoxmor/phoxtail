"""v1 of the CMS API.

Aggregates CMS sub-routers into a single ``Router`` contributed to the
auto-mount machinery at ``/api/cms/v1/`` via ``PhoxtailCmsConfig``.
"""

from __future__ import annotations

from ninja import Router

from phoxtail.cms.api.v1.site_setting_fonts import router as fonts_router
from phoxtail.cms.api.v1.site_setting_palettes import router as palettes_router
from phoxtail.cms.api.v1.site_settings import router as site_settings_router

router = Router()
router.add_router("/site-settings", site_settings_router)
router.add_router("/site-settings", fonts_router)
router.add_router("/site-settings", palettes_router)
