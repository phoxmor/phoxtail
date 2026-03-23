"""
Layered schema blocks with depth-limited nesting.

These blocks enable nested structures (structs within structs) while preventing
infinite recursion through explicit depth layers.

Layer hierarchy:
- Layer 0 (top): StructSchemaBlock, StreamSchemaBlock,
  ListStructSchemaBlock (in structures.py and streams.py)
- Layer 1: StructSchemaBlockL1, StreamSchemaBlockL1,
  ListStructSchemaBlockL1 (can contain L2 blocks)
- Layer 2: StructSchemaBlockL2
  (terminal layer - fields only, no further nesting)

Example - Pricing block structure:
- stream (plans) → StreamSchemaBlock (L0)
  - struct (plan) → StructSchemaBlockL1
    - fields: name, price, etc.
    - stream (features) → StreamSchemaBlockL1
      - struct (feature) → StructSchemaBlockL2
        - fields: feature, is_enabled
"""

from wagtail.blocks import BooleanBlock, IntegerBlock, StreamBlock

from .base import FieldSchemaBlock
from .fields import FIELD_BLOCK_CHOICES

# ==============================================================================
# LAYER 2: TERMINAL BLOCKS (Fields only, no further nesting)
# ==============================================================================


class StructSchemaBlockL2(FieldSchemaBlock):
    """
    Layer 2 (terminal) structure block - contains fields only.

    This is the innermost nesting level. Use when you need a struct
    inside another nested struct (e.g., features within a pricing plan).
    """

    blocks = StreamBlock(
        FIELD_BLOCK_CHOICES.choices,
        min_num=1,
        help_text="Fields in this structure (innermost layer, no further nesting)",
    )

    collapsed = BooleanBlock(
        required=False,
        default=False,
        help_text="Start with this structure collapsed in the editor",
    )

    class Meta:
        icon = "snippet"
        label = "Structure (L2)"
        group = "Layers"


# ==============================================================================
# LAYER 1: NESTED BLOCKS (Can contain L2 terminal blocks)
# ==============================================================================


class StructSchemaBlockL1(FieldSchemaBlock):
    """
    Layer 1 structure block - can contain fields and L2 structures.

    Use when you need a struct inside a top-level stream or struct
    (e.g., a plan struct inside a plans stream).
    """

    blocks = StreamBlock(
        FIELD_BLOCK_CHOICES.choices
        + [
            ("struct", StructSchemaBlockL2()),
        ],
        min_num=1,
        help_text="Fields and structures (can nest one more layer)",
    )

    collapsed = BooleanBlock(
        required=False,
        default=False,
        help_text="Start with this structure collapsed in the editor",
    )

    class Meta:
        icon = "widgets"
        label = "Structure (L1)"
        group = "Layers"


class StreamSchemaBlockL1(FieldSchemaBlock):
    """
    Layer 1 stream block - can contain fields and L2 structures.

    Use when you need a repeating stream inside a top-level struct
    (e.g., a features stream inside a plan struct).
    """

    blocks = StreamBlock(
        FIELD_BLOCK_CHOICES.choices
        + [
            ("struct", StructSchemaBlockL2()),
        ],
        min_num=1,
        help_text="Blocks in this stream (can contain L2 structures)",
    )

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

    collapsed = BooleanBlock(
        required=False,
        default=False,
        help_text="Start with all blocks collapsed in the editor",
    )

    class Meta:
        icon = "list-ul"
        label = "Stream (L1)"
        group = "Layers"


class ListStructSchemaBlockL1(FieldSchemaBlock):
    """
    Layer 1 list of structures block - can contain fields and L2 structures.

    Use when you need a repeating list of structured items inside a top-level struct
    (e.g., a buttons list inside a plan struct).
    """

    blocks = StreamBlock(
        FIELD_BLOCK_CHOICES.choices
        + [
            ("struct", StructSchemaBlockL2()),
        ],
        min_num=1,
        help_text="Fields in each list item (can contain L2 structures)",
    )

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

    collapsed = BooleanBlock(
        required=False,
        default=False,
        help_text="Start with all list items collapsed in the editor",
    )

    class Meta:
        icon = "category"
        label = "List of Structures (L1)"
        group = "Layers"


# ==============================================================================
# LAYER BLOCK CHOICES REGISTRY
# ==============================================================================


class LAYER_BLOCK_CHOICES:
    """
    Registry for layer schema blocks at different depth levels.

    Layer 1 blocks can be used inside top-level (L0) structures.
    Layer 2 blocks can be used inside L1 structures.
    """

    # Layer 2 (terminal - fields only)
    STRUCT_L2 = ("struct", StructSchemaBlockL2())

    # Layer 1 (can contain L2)
    STRUCT_L1 = ("struct", StructSchemaBlockL1())
    STREAM_L1 = ("stream", StreamSchemaBlockL1())
    LIST_STRUCT_L1 = ("list_struct", ListStructSchemaBlockL1())
