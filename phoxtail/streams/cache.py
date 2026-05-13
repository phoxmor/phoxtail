"""
In-memory caches for the dynamic blocks system.
"""

import logging

from django.template import Template

logger = logging.getLogger(__name__)

_block_cache: dict = {}
_template_cache: dict = {}
_default_variant_cache: dict = {}
_dynamic_blocks_cache = None
_shared_blocks_cache = None
_page_type_blocks_cache: dict = {}
_shared_block_cache: dict = {}
_cache_generation: int = 0


def get_block_by_identifier(identifier: str):
    if identifier not in _block_cache:
        from phoxtail.streams.models import Block

        try:
            _block_cache[identifier] = Block.objects.get(identifier=identifier)
        except Block.DoesNotExist:
            logger.warning("Block with identifier '%s' not found", identifier)
            return None

    return _block_cache[identifier]


def get_default_variant(block_identifier: str):
    if block_identifier not in _default_variant_cache:
        from phoxtail.streams.models import BlockVariant

        _default_variant_cache[block_identifier] = BlockVariant.objects.filter(
            block__identifier=block_identifier, is_default=True
        ).first()
    return _default_variant_cache[block_identifier]


def get_compiled_template(template_string: str) -> Template:
    cache_key = hash(template_string)
    if cache_key not in _template_cache:
        _template_cache[cache_key] = Template(template_string)
    return _template_cache[cache_key]


def get_cached_dynamic_blocks() -> list:
    global _dynamic_blocks_cache
    if _dynamic_blocks_cache is None:
        from phoxtail.streams.blocks.factory import build_dynamic_blocks

        _dynamic_blocks_cache = build_dynamic_blocks()
    return _dynamic_blocks_cache


def get_cached_shared_blocks() -> list:
    global _shared_blocks_cache
    if _shared_blocks_cache is None:
        from phoxtail.streams.blocks.factory import build_shared_blocks

        _shared_blocks_cache = build_shared_blocks()
    return _shared_blocks_cache


def get_cached_blocks_for_page_type(content_type_id) -> list:
    global _page_type_blocks_cache
    if content_type_id not in _page_type_blocks_cache:
        from phoxtail.streams.blocks.factory import build_blocks_for_page_type

        _page_type_blocks_cache[content_type_id] = build_blocks_for_page_type(content_type_id)
    return _page_type_blocks_cache[content_type_id]


def get_shared_block(block_identifier: str, site, locale):
    site_id = site.pk if site else None
    locale_id = locale.pk if locale else None
    cache_key = (block_identifier, site_id, locale_id)

    if cache_key not in _shared_block_cache:
        from phoxtail.streams.models import SharedBlock

        _shared_block_cache[cache_key] = (
            SharedBlock.objects.filter(
                block__identifier=block_identifier,
                site_id=site_id,
                locale_id=locale_id,
            )
            .select_related("block")
            .first()
        )
    return _shared_block_cache[cache_key]


def get_cache_generation() -> int:
    return _cache_generation


def clear_block_cache(**kwargs):
    global _dynamic_blocks_cache, _shared_blocks_cache, _cache_generation, _page_type_blocks_cache
    _block_cache.clear()
    _default_variant_cache.clear()
    _template_cache.clear()
    _dynamic_blocks_cache = None
    _shared_blocks_cache = None
    _page_type_blocks_cache = {}
    _cache_generation += 1
    logger.debug("All block caches cleared (generation %d)", _cache_generation)


def clear_shared_block_cache(**kwargs):
    _shared_block_cache.clear()
    logger.debug("Shared block cache cleared")
