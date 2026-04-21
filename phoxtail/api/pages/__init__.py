"""Core pages domain HTTP API.

All concrete routing lives under versioned sub-packages
(:mod:`phoxtail.api.pages.v1`). This package init is intentionally
empty so that ``import phoxtail.api.pages`` has no side effects — the
single aggregated router is imported explicitly by :mod:`phoxtail.api`.
"""
