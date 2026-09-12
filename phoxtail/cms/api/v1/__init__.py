"""v1 of the CMS API.

Everything that reads or writes a Wagtail entity: pages and their bodies and
blocks, collections, page types, locales, sites, and the per-site settings that
carry a site's fonts and palettes.

The sub-routers are mounted in the order the pages domain reads best — the
three ``/pages`` routers are one resource split across three modules by
concern, not three resources.
"""

from __future__ import annotations

from ninja import Router

from phoxtail.cms.api.v1.blocks import router as blocks_router
from phoxtail.cms.api.v1.body import router as body_router
from phoxtail.cms.api.v1.collections import router as collections_router
from phoxtail.cms.api.v1.locales import router as locales_router
from phoxtail.cms.api.v1.page_types import router as page_types_router
from phoxtail.cms.api.v1.pages import router as pages_router
from phoxtail.cms.api.v1.site_setting_fonts import router as fonts_router
from phoxtail.cms.api.v1.site_setting_palettes import router as palettes_router
from phoxtail.cms.api.v1.site_settings import router as site_settings_router
from phoxtail.cms.api.v1.sites import router as sites_router

router = Router()
# /pages/ and /pages/{id}/* live on pages_router.
router.add_router("/pages", pages_router)
# Body endpoints: /pages/{id}/body/...
router.add_router("/pages", body_router)
# Per-block endpoints: /pages/{id}/blocks/...
router.add_router("/pages", blocks_router)
router.add_router("/collections", collections_router)
router.add_router("/page-types", page_types_router)
router.add_router("/locales", locales_router)
router.add_router("/sites", sites_router)
router.add_router("/site-settings", site_settings_router)
router.add_router("/site-settings", fonts_router)
router.add_router("/site-settings", palettes_router)
