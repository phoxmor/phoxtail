"""
Structure schema blocks that compose other blocks.

These meta-blocks define structures that contain multiple fields:
- StructSchemaBlock: Groups fields together (supports 2 layers of nesting)
- ListFieldSchemaBlock: Repeating list of a single field type
- ListStructSchemaBlock: Repeating list of structured items
  (supports 2 layers of nesting)

Nesting is achieved through depth-limited layer blocks from layers.py:
- Layer 0: StructSchemaBlock can contain L1 blocks
  (StructSchemaBlockL1, StreamSchemaBlockL1)
- Layer 1: L1 blocks can contain L2 blocks (StructSchemaBlockL2)
- Layer 2: StructSchemaBlockL2 contains only fields (no further nesting)
"""

from wagtail.blocks import BooleanBlock, IntegerBlock, StreamBlock

from .base import FieldSchemaBlock
from .fields import FIELD_BLOCK_CHOICES
from .layers import LAYER_BLOCK_CHOICES


class StructSchemaBlock(FieldSchemaBlock):
    """
    Meta-block that defines a structure (group of fields).

    Used to describe blocks like 'text_section' which contains multiple fields.
    Supports up to 2 layers of nested structures for complex blocks like pricing tables.
    """

    blocks = StreamBlock(
        FIELD_BLOCK_CHOICES.choices
        + [
            # Layer 1 blocks (depth-limited to prevent recursion)
            LAYER_BLOCK_CHOICES.STRUCT_L1,
            LAYER_BLOCK_CHOICES.STREAM_L1,
            LAYER_BLOCK_CHOICES.LIST_STRUCT_L1,
        ],
        min_num=1,
        help_text="Blocks that compose this structure (supports nested structures)",
    )

    # UI configuration
    collapsed = BooleanBlock(
        required=False,
        default=False,
        help_text="Start with this structure collapsed in the editor",
    )

    class Meta:
        icon = "widgets"
        label = "Structure"
        group = "Structures"


class ListFieldSchemaBlock(FieldSchemaBlock):
    """
    Meta-block that defines a repeating list of simple field items.

    Used to describe simple lists like 'gallery_images', 'tags', 'links', etc.
    Each item in the list is a single field (image, text, URL, etc.).

    Unlike ListStructSchemaBlock (which has multiple fields per
    item), this allows configuring a single field type with its
    own parameters (max_length, help_text, etc.).
    """

    blocks = StreamBlock(
        FIELD_BLOCK_CHOICES.choices,
        min_num=1,
        max_num=1,
        help_text=(
            "Define the field type and configuration for "
            "each item in this list (add exactly one)"
        ),
    )

    # List constraints
    min_num = IntegerBlock(
        required=False,
        min_value=0,
        help_text="Minimum number of items required (optional)",
    )
    max_num = IntegerBlock(
        required=False,
        min_value=1,
        help_text="Maximum number of items allowed (optional)",
    )

    # UI configuration
    collapsed = BooleanBlock(
        required=False,
        default=False,
        help_text="Start with all list items collapsed in the editor",
    )

    class Meta:
        icon = "list"
        label = "List of Fields"
        group = "Structures"


class ListStructSchemaBlock(FieldSchemaBlock):
    """
    Meta-block that defines a repeating list of structured items.

    Used to describe complex lists like 'team_members', 'buttons', 'features', etc.
    Each item in the list is a structured object with multiple fields.
    Supports up to 2 layers of nested structures.
    """

    blocks = StreamBlock(
        FIELD_BLOCK_CHOICES.choices
        + [
            # Layer 1 blocks (depth-limited to prevent recursion)
            LAYER_BLOCK_CHOICES.STRUCT_L1,
            LAYER_BLOCK_CHOICES.STREAM_L1,
            LAYER_BLOCK_CHOICES.LIST_STRUCT_L1,
        ],
        min_num=1,
        help_text=(
            "Blocks that define the structure of each "
            "list item (supports nested structures)"
        ),
    )

    # List constraints
    min_num = IntegerBlock(
        required=False,
        min_value=0,
        help_text="Minimum number of items required (optional)",
    )
    max_num = IntegerBlock(
        required=False,
        min_value=1,
        help_text="Maximum number of items allowed (optional)",
    )

    # UI configuration
    collapsed = BooleanBlock(
        required=False,
        default=False,
        help_text="Start with all list items collapsed in the editor",
    )

    class Meta:
        icon = "category"
        label = "List of Structures"
        group = "Structures"


# ==============================================================================
# STRUCTURE BLOCK CHOICES REGISTRY
# ==============================================================================


class STRUCTURE_BLOCK_CHOICES:
    """
    Registry for structure schema blocks.

    Each attribute is a tuple of (identifier, block_instance)
    ready for use in StreamBlock.

    Usage::

        from phoxtail.streams.blocks.schema import (
            STRUCTURE_BLOCK_CHOICES,
        )

        blocks = StreamBlock([
            STRUCTURE_BLOCK_CHOICES.STRUCT,
            STRUCTURE_BLOCK_CHOICES.LIST_FIELD,
            STRUCTURE_BLOCK_CHOICES.LIST_STRUCT,
        ])
    """

    STRUCT = ("struct", StructSchemaBlock())
    LIST_FIELD = ("list_field", ListFieldSchemaBlock())
    LIST_STRUCT = ("list_struct", ListStructSchemaBlock())
