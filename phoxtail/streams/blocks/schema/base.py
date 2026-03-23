"""
Base class for all field schema blocks.

This module contains the abstract base class that all schema blocks inherit from,
providing common parameters like name, required, help_text, and icon.
"""

from wagtail.blocks import BooleanBlock, CharBlock, StructBlock


class FieldSchemaBlock(StructBlock):
    """
    Abstract base class for all field schema blocks.

    All field types include these common parameters:
    - name: The field identifier (e.g., 'title', 'subtitle')
    - required: Whether the field is required
    - help_text: Help text shown to content editors
    - icon: Wagtail icon name for the field
    """

    name = CharBlock(
        max_length=100,
        help_text=(
            "Field name (e.g., 'title', 'subtitle'). Use lowercase with underscores."
        ),
    )
    required = BooleanBlock(
        required=False, default=True, help_text="Is this field required?"
    )
    help_text = CharBlock(
        required=False,
        max_length=255,
        help_text="Help text shown to content editors",
    )
    icon = CharBlock(
        required=False,
        max_length=100,
        help_text=(
            "Wagtail icon name (e.g., 'image', 'doc-full', "
            "'media'). Can use default Wagtail icons or "
            "custom SVG icons."
        ),
    )
