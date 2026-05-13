"""
Custom field implementations for dynamic block support.
"""

from wagtail.blocks import StreamBlock
from wagtail.fields import StreamField


def get_shared_blocks():
    """
    Callable for SharedBlock's StreamField.

    Returns shared blocks with full content fields (no variant chooser),
    intended for admins to fill site-level content.

    Defined here (not in factory.py) to avoid circular imports:
    models.py → fields.py (import time) → cache.py → factory.py → models.py (runtime)
    """
    from phoxtail.streams.cache import get_cached_shared_blocks

    return get_cached_shared_blocks()


class SchemaStreamField(StreamField):
    """
    A StreamField that generates blocks from schema definitions.

    This allows blocks to be defined by schemas (stored in Block models) and
    generated dynamically at runtime, enabling database-driven block architecture
    while still working with Django's migration system.
    """

    def __init__(self, block_types_arg, **kwargs):
        self._block_types_callable = block_types_arg if callable(block_types_arg) else None

        self._stream_block_kwargs = {}
        stream_block_params = ["min_num", "max_num", "block_counts", "collapsed"]
        for param in stream_block_params:
            if param in kwargs:
                self._stream_block_kwargs[param] = kwargs.pop(param)

        self._cached_stream_block = None
        self._cache_generation = -1

        super().__init__([], **kwargs)

    @property
    def stream_block(self):
        if self._block_types_callable:
            from phoxtail.streams.cache import get_cache_generation

            current_generation = get_cache_generation()
            if self._cached_stream_block is None or self._cache_generation != current_generation:
                block_types = self._block_types_callable()

                stream_block_kwargs = {
                    "required": not self.blank,
                    **self._stream_block_kwargs,
                }
                self._cached_stream_block = StreamBlock(block_types, **stream_block_kwargs)
                self._cache_generation = current_generation

            return self._cached_stream_block
        else:
            return super().stream_block

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        return name, path, [[]], kwargs


SharedBlockStreamField = SchemaStreamField(
    get_shared_blocks,
    null=True,
    blank=True,
    max_num=1,
)
