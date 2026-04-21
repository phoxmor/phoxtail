"""v1 of the blog API.

Aggregates all blog-specific sub-routers. Mounted automatically at
``/api/blog/v1/`` via ``PhoxtailBlogConfig.api_version_router`` —
no change to ``phoxtail.api`` required.
"""

from __future__ import annotations

from ninja import Router

from phoxtail.blog.api.v1.authors import router as authors_router

router = Router()
router.add_router("/authors", authors_router)
