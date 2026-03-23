"""
Schema module for database-driven block definitions.

This module contains all schema blocks used to define the structure of dynamic blocks.

Exports:
- Base class: FieldSchemaBlock
- 24 Field schema blocks (CharSchemaBlock, TextSchemaBlock,
  VideoChooserSchemaBlock, etc.)
- 3 Structure schema blocks (StructSchemaBlock,
  ListFieldSchemaBlock, ListStructSchemaBlock)
- 1 Stream schema block (StreamSchemaBlock)
- 4 Layer blocks for nested structures (StructSchemaBlockL1, StructSchemaBlockL2, etc.)
- 3 Registries: FIELD_BLOCK_CHOICES, STRUCTURE_BLOCK_CHOICES, LAYER_BLOCK_CHOICES
"""

# Base class
from .base import FieldSchemaBlock

# Field schema blocks (24 types)
from .fields import (
    FIELD_BLOCK_CHOICES,
    BlockQuoteSchemaBlock,
    BooleanSchemaBlock,
    CharSchemaBlock,
    ChoiceSchemaBlock,
    DateSchemaBlock,
    DateTimeSchemaBlock,
    DecimalSchemaBlock,
    DocumentChooserSchemaBlock,
    EmailSchemaBlock,
    EmbedSchemaBlock,
    FloatSchemaBlock,
    ImageChooserSchemaBlock,
    ImageSchemaBlock,
    IntegerSchemaBlock,
    MultipleChoiceSchemaBlock,
    PageChooserSchemaBlock,
    RawHTMLSchemaBlock,
    RegexSchemaBlock,
    RichTextSchemaBlock,
    SnippetChooserSchemaBlock,
    TextSchemaBlock,
    TimeSchemaBlock,
    URLSchemaBlock,
    VideoChooserSchemaBlock,
)

# Layer blocks (depth-limited for recursion prevention)
from .layers import (
    LAYER_BLOCK_CHOICES,
    ListStructSchemaBlockL1,
    StreamSchemaBlockL1,
    StructSchemaBlockL1,
    StructSchemaBlockL2,
)

# Stream schema block (1 type)
from .streams import StreamSchemaBlock

# Structure schema blocks (3 types)
from .structures import (
    STRUCTURE_BLOCK_CHOICES,
    ListFieldSchemaBlock,
    ListStructSchemaBlock,
    StructSchemaBlock,
)

__all__ = [
    # Base
    "FieldSchemaBlock",
    # Registries
    "FIELD_BLOCK_CHOICES",
    "STRUCTURE_BLOCK_CHOICES",
    "LAYER_BLOCK_CHOICES",
    # Field blocks
    "CharSchemaBlock",
    "TextSchemaBlock",
    "EmailSchemaBlock",
    "URLSchemaBlock",
    "BlockQuoteSchemaBlock",
    "RawHTMLSchemaBlock",
    "IntegerSchemaBlock",
    "FloatSchemaBlock",
    "DecimalSchemaBlock",
    "BooleanSchemaBlock",
    "DateSchemaBlock",
    "TimeSchemaBlock",
    "DateTimeSchemaBlock",
    "RichTextSchemaBlock",
    "RegexSchemaBlock",
    "ChoiceSchemaBlock",
    "MultipleChoiceSchemaBlock",
    "PageChooserSchemaBlock",
    "DocumentChooserSchemaBlock",
    "ImageChooserSchemaBlock",
    "ImageSchemaBlock",
    "SnippetChooserSchemaBlock",
    "VideoChooserSchemaBlock",
    "EmbedSchemaBlock",
    # Structure blocks
    "StructSchemaBlock",
    "ListFieldSchemaBlock",
    "ListStructSchemaBlock",
    # Stream blocks
    "StreamSchemaBlock",
    # Layer blocks (depth-limited)
    "StructSchemaBlockL1",
    "StructSchemaBlockL2",
    "StreamSchemaBlockL1",
    "ListStructSchemaBlockL1",
]
