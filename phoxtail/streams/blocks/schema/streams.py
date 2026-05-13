"""
Stream schema blocks for mixed-content streams.

StreamSchemaBlock allows editors to choose from multiple different block types
and mix them freely in any order (equivalent to Wagtail's StreamBlock).
"""

from wagtail.blocks import BooleanBlock, IntegerBlock, StreamBlock, TextBlock

from .base import FieldSchemaBlock
from .fields import FIELD_BLOCK_CHOICES
from .structures import STRUCTURE_BLOCK_CHOICES


class StreamSchemaBlock(FieldSchemaBlock):
    """
    Meta-block that defines a free-form mixed-content stream.

    Unlike ListBlock (homogeneous items), StreamSchemaBlock allows editors to choose
    from multiple different block types and mix them freely in any order.
    This is equivalent to Wagtail's StreamBlock.

    Use Cases:
    - Media gallery with images OR videos OR captions (mixed)
    - Content sections with various block types (heading, paragraph, image, embed)
    - Flexible page builders where block order and type vary
    - Any scenario requiring heterogeneous repeating content

    Example: A "content_blocks" stream might allow:
    - Heading (char_field)
    - Paragraph (rich_text_field)
    - Image (image_chooser_field)
    - Video (embed_field)
    - Quote (struct with author + text)

    Editors can add these in any combination and order.
    """

    blocks = StreamBlock(
        FIELD_BLOCK_CHOICES.choices
        + [
            # Structures - allows nested complexity
            STRUCTURE_BLOCK_CHOICES.STRUCT,
            STRUCTURE_BLOCK_CHOICES.LIST_FIELD,
            STRUCTURE_BLOCK_CHOICES.LIST_STRUCT,
            # Note: Recursive stream nesting is possible but creates circular dependency
            # Can be added later with lazy loading: ("stream", StreamSchemaBlock())
        ],
        min_num=1,
        help_text=("Blocks that can be used in this stream. Editors can add any of these in any order."),
    )

    # Stream constraints
    min_num = IntegerBlock(
        required=False,
        min_value=0,
        help_text="Minimum number of blocks required (optional)",
    )
    max_num = IntegerBlock(
        required=False,
        min_value=1,
        help_text="Maximum number of blocks allowed (optional)",
    )

    block_counts = TextBlock(
        required=False,
        help_text=(
            "Per-block-type limits in JSON format (optional)\n"
            "Example:\n"
            "{\n"
            '  "image_chooser_field": {"min_num": 1, "max_num": 5},\n'
            '  "embed_field": {"max_num": 2}\n'
            "}"
        ),
    )

    collapsed = BooleanBlock(
        required=False,
        default=False,
        help_text="Start with all blocks collapsed in the editor",
    )

    search_index = BooleanBlock(
        required=False,
        default=True,
        help_text="Include this stream content in search indexing",
    )

    class Meta:
        icon = "graph-3"
        label = "Stream"
        group = "Structures"
