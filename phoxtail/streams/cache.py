"""
In-memory caches for the dynamic blocks system.

Cross-process invalidation: a shared Redis counter acts as a generation
doorbell. Each worker reads the counter on every SchemaStreamField access
and self-clears if it has fallen behind. One Redis GET per access (~0.1ms);
the per-process dicts remain the fast path.

Graceful fallback: if Redis is unavailable (bare runserver without Docker),
invalidation is process-local only — the same behaviour as before this change.
"""

import logging
import os

from django.template import Template

logger = logging.getLogger(__name__)

_block_cache: dict = {}
_template_cache: dict = {}
_default_variant_cache: dict = {}
_dynamic_blocks_cache = None
_shared_blocks_cache = None
_page_type_blocks_cache: dict = {}
_shared_block_cache: dict = {}

_local_generation: int = 0  # generation this process's caches currently reflect

_REDIS_KEY = "phoxtail:cache_generation"
_redis_client = None
_redis_probed: bool = False  # True after first connection attempt


def _get_redis():
    global _redis_client, _redis_probed
    if _redis_probed and _redis_client is None:
        return None
    if _redis_client is not None:
        return _redis_client
    _redis_probed = True
    try:
        import redis

        url = os.environ.get("REDIS_URL", "redis://redis:6379/0")
        client = redis.from_url(url, socket_connect_timeout=1, socket_timeout=0.1)
        client.ping()
        _redis_client = client
        logger.debug("Redis connected for block cache generation counter")
        return _redis_client
    except Exception:
        logger.warning("Redis unavailable — block cache invalidation is process-local only")
        return None


def _get_redis_generation() -> int:
    r = _get_redis()
    if r is None:
        return _local_generation
    try:
        val = r.get(_REDIS_KEY)
        return int(val) if val is not None else 0
    except Exception:
        return _local_generation


def _incr_redis_generation() -> int:
    r = _get_redis()
    if r is None:
        return _local_generation + 1
    try:
        return int(r.incr(_REDIS_KEY))
    except Exception:
        return _local_generation + 1


def _clear_local_caches():
    global _dynamic_blocks_cache, _shared_blocks_cache, _page_type_blocks_cache
    _block_cache.clear()
    _default_variant_cache.clear()
    _template_cache.clear()
    _shared_block_cache.clear()
    _dynamic_blocks_cache = None
    _shared_blocks_cache = None
    _page_type_blocks_cache = {}


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
    get_cache_generation()  # self-invalidate regardless of render order
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
    global _local_generation
    redis_gen = _get_redis_generation()
    if redis_gen != _local_generation:
        _clear_local_caches()
        _local_generation = redis_gen
        logger.debug("Block caches invalidated by Redis generation change (generation %d)", redis_gen)
    return _local_generation


def clear_block_cache(**kwargs):
    global _local_generation
    new_gen = _incr_redis_generation()
    _clear_local_caches()
    _local_generation = new_gen
    logger.debug("Block caches cleared (generation %d)", _local_generation)


def clear_shared_block_cache(**kwargs):
    global _local_generation
    new_gen = _incr_redis_generation()
    _clear_local_caches()
    _local_generation = new_gen
    logger.debug("Shared block cache cleared (generation %d)", _local_generation)
