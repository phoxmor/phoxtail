"""
Signal handlers for cache invalidation in the dynamic blocks system.
"""

from django.db.models.signals import post_delete, post_save


def _clear_shared_cache_if_page_referenced(sender, instance, **kwargs):
    from django.contrib.contenttypes.models import ContentType
    from wagtail.models import ReferenceIndex

    from phoxtail.streams.cache import clear_shared_block_cache
    from phoxtail.streams.models import SharedBlock

    shared_block_ct = ContentType.objects.get_for_model(SharedBlock)
    is_referenced = (
        ReferenceIndex.get_references_to(instance)
        .filter(base_content_type=shared_block_ct)
        .exists()
    )
    if is_referenced:
        clear_shared_block_cache()


def connect_cache_signals():
    from wagtail.models import Page
    from wagtail.signals import page_published, page_unpublished

    from phoxtail.streams.cache import clear_block_cache, clear_shared_block_cache
    from phoxtail.streams.models import Block, BlockVariant, SharedBlock

    post_save.connect(clear_block_cache, sender=Block)
    post_delete.connect(clear_block_cache, sender=Block)
    post_save.connect(clear_block_cache, sender=BlockVariant)
    post_delete.connect(clear_block_cache, sender=BlockVariant)
    post_save.connect(clear_shared_block_cache, sender=SharedBlock)
    post_delete.connect(clear_shared_block_cache, sender=SharedBlock)

    page_published.connect(_clear_shared_cache_if_page_referenced)
    page_unpublished.connect(_clear_shared_cache_if_page_referenced)
    post_delete.connect(_clear_shared_cache_if_page_referenced, sender=Page)
