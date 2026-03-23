"""
All 24 field schema blocks.

These are meta-blocks used to define the structure of other blocks.
Each corresponds to a Wagtail field block type.

Organized by category:
- Text Fields (6 types)
- Numeric Fields (3 types)
- Boolean (1 type)
- Date/Time (3 types)
- Rich Content (1 type)
- Advanced (3 types)
- Choosers (6 types)
- Embed & Media (1 type)
"""

from wagtail.blocks import (
    BooleanBlock,
    CharBlock,
    IntegerBlock,
    ListBlock,
    MultipleChoiceBlock,
    StructBlock,
    TextBlock,
)

from .base import FieldSchemaBlock

# ==============================================================================
# TEXT FIELD SCHEMA BLOCKS
# ==============================================================================


class CharSchemaBlock(FieldSchemaBlock):
    """Single line text input field."""

    min_length = IntegerBlock(
        required=False,
        min_value=0,
        help_text="Minimum character length (optional)",
    )
    max_length = IntegerBlock(
        required=False,
        min_value=1,
        help_text="Maximum character length (optional)",
    )
    search_index = BooleanBlock(
        required=False,
        default=True,
        help_text="Index this field content for searching",
    )

    class Meta:
        label = "Single Line Text (Char)"
        icon = "short-text"
        group = "Text Fields"


class TextSchemaBlock(FieldSchemaBlock):
    """Multi-line text area field."""

    min_length = IntegerBlock(
        required=False,
        min_value=0,
        help_text="Minimum character length (optional)",
    )
    max_length = IntegerBlock(
        required=False,
        min_value=1,
        help_text="Maximum character length (optional)",
    )
    rows = IntegerBlock(
        required=False,
        min_value=1,
        help_text="Number of visible text lines (optional)",
    )
    search_index = BooleanBlock(
        required=False,
        default=True,
        help_text="Index this field content for searching",
    )

    class Meta:
        label = "Multi-line Text"
        icon = "subject"
        group = "Text Fields"


class EmailSchemaBlock(FieldSchemaBlock):
    """Email address field with validation."""

    class Meta:
        label = "Email"
        icon = "mail"
        group = "Text Fields"


class URLSchemaBlock(FieldSchemaBlock):
    """URL field with validation."""

    min_length = IntegerBlock(
        required=False,
        min_value=0,
        help_text="Minimum character length (optional)",
    )
    max_length = IntegerBlock(
        required=False,
        min_value=1,
        help_text="Maximum character length (optional)",
    )

    class Meta:
        label = "URL"
        icon = "link"
        group = "Text Fields"


class BlockQuoteSchemaBlock(FieldSchemaBlock):
    """Block quote text field."""

    min_length = IntegerBlock(
        required=False,
        min_value=0,
        help_text="Minimum character length (optional)",
    )
    max_length = IntegerBlock(
        required=False,
        min_value=1,
        help_text="Maximum character length (optional)",
    )

    class Meta:
        label = "Block Quote"
        icon = "openquote"
        group = "Text Fields"


class RawHTMLSchemaBlock(FieldSchemaBlock):
    """Raw HTML field (unescaped)."""

    min_length = IntegerBlock(
        required=False,
        min_value=0,
        help_text="Minimum character length (optional)",
    )
    max_length = IntegerBlock(
        required=False,
        min_value=1,
        help_text="Maximum character length (optional)",
    )

    class Meta:
        label = "Raw HTML"
        icon = "code"
        group = "Text Fields"


# ==============================================================================
# NUMERIC FIELD SCHEMA BLOCKS
# ==============================================================================


class IntegerSchemaBlock(FieldSchemaBlock):
    """Whole number input field."""

    min_value = IntegerBlock(
        required=False,
        help_text="Minimum value (optional)",
    )
    max_value = IntegerBlock(
        required=False,
        help_text="Maximum value (optional)",
    )

    class Meta:
        label = "Integer"
        icon = "form"
        group = "Numeric Fields"


class FloatSchemaBlock(FieldSchemaBlock):
    """Floating-point number input field."""

    min_value = IntegerBlock(
        required=False,
        help_text="Minimum value (optional)",
    )
    max_value = IntegerBlock(
        required=False,
        help_text="Maximum value (optional)",
    )

    class Meta:
        label = "Float"
        icon = "form"
        group = "Numeric Fields"


class DecimalSchemaBlock(FieldSchemaBlock):
    """Decimal number field with precision control."""

    min_value = IntegerBlock(
        required=False,
        help_text="Minimum value (optional)",
    )
    max_value = IntegerBlock(
        required=False,
        help_text="Maximum value (optional)",
    )
    max_digits = IntegerBlock(
        required=False,
        min_value=1,
        help_text="Total number of digits (optional)",
    )
    decimal_places = IntegerBlock(
        required=False,
        min_value=0,
        help_text="Number of decimal places (optional)",
    )

    class Meta:
        label = "Decimal"
        icon = "form"
        group = "Numeric Fields"


# ==============================================================================
# BOOLEAN FIELD SCHEMA BLOCKS
# ==============================================================================


class BooleanSchemaBlock(FieldSchemaBlock):
    """Checkbox field for true/false values."""

    # Note: BooleanBlock in Wagtail doesn't use 'required' parameter
    # It's always optional (checkbox unchecked = False)

    class Meta:
        label = "Boolean (Checkbox)"
        icon = "check-box"
        group = "Boolean & Logic"


# ==============================================================================
# DATE/TIME FIELD SCHEMA BLOCKS
# ==============================================================================


class DateSchemaBlock(FieldSchemaBlock):
    """Date picker field."""

    format = CharBlock(
        required=False,
        max_length=50,
        help_text="Date format (from Django's DATE_INPUT_FORMATS, optional)",
    )

    class Meta:
        label = "Date"
        icon = "date"
        group = "Date & Time"


class TimeSchemaBlock(FieldSchemaBlock):
    """Time picker field."""

    format = CharBlock(
        required=False,
        max_length=50,
        help_text="Time format (from Django's TIME_INPUT_FORMATS, optional)",
    )

    class Meta:
        label = "Time"
        icon = "time"
        group = "Date & Time"


class DateTimeSchemaBlock(FieldSchemaBlock):
    """Combined date and time picker field."""

    format = CharBlock(
        required=False,
        max_length=50,
        help_text="DateTime format (from Django's DATETIME_INPUT_FORMATS, optional)",
    )

    class Meta:
        label = "Date & Time"
        icon = "date"
        group = "Date & Time"


# ==============================================================================
# RICH CONTENT FIELD SCHEMA BLOCKS
# ==============================================================================


class RichTextSchemaBlock(FieldSchemaBlock):
    """WYSIWYG rich text editor field."""

    min_length = IntegerBlock(
        required=False,
        min_value=0,
        help_text="Minimum character length (text-only, optional)",
    )
    max_length = IntegerBlock(
        required=False,
        min_value=1,
        help_text="Maximum character length (text-only, optional)",
    )
    search_index = BooleanBlock(
        required=False,
        default=True,
        help_text="Index this field content for searching",
    )
    editor = CharBlock(
        required=False,
        max_length=100,
        help_text="Rich text editor selection (optional)",
    )
    features = MultipleChoiceBlock(
        required=False,
        choices=[
            ("h1", "Heading 1"),
            ("h2", "Heading 2"),
            ("h3", "Heading 3"),
            ("h4", "Heading 4"),
            ("h5", "Heading 5"),
            ("h6", "Heading 6"),
            ("bold", "Bold"),
            ("italic", "Italic"),
            ("underline", "Underline"),
            ("strikethrough", "Strikethrough"),
            ("ol", "Ordered List"),
            ("ul", "Unordered List"),
            ("link", "Link"),
            ("document-link", "Document Link"),
            ("blockquote", "Block Quote"),
            ("superscript", "Superscript"),
            ("subscript", "Subscript"),
            ("code", "Code"),
            ("hr", "Horizontal Rule"),
            ("embed", "Embed"),
            ("image", "Image"),
        ],
        help_text="Select which formatting features should be available in the editor",
    )

    class Meta:
        label = "Rich Text Editor"
        icon = "pilcrow"
        group = "Rich Content"


# ==============================================================================
# REGEX FIELD SCHEMA BLOCKS
# ==============================================================================


class RegexSchemaBlock(FieldSchemaBlock):
    """Text field with custom regex validation."""

    regex = CharBlock(
        max_length=500,
        help_text="Regular expression pattern to validate against",
    )
    min_length = IntegerBlock(
        required=False,
        min_value=0,
        help_text="Minimum character length (optional)",
    )
    max_length = IntegerBlock(
        required=False,
        min_value=1,
        help_text="Maximum character length (optional)",
    )
    error_messages = TextBlock(
        required=False,
        help_text=(
            "Error messages in JSON format (optional)\\n"
            '{"required": "This field is required", "invalid": "Invalid format"}'
        ),
    )

    class Meta:
        label = "Regular Expression"
        icon = "regular-expression"
        group = "Advanced Fields"


# ==============================================================================
# CHOICE FIELD SCHEMA BLOCKS
# ==============================================================================


_ChoiceItemBlock = StructBlock(
    [
        (
            "value",
            CharBlock(
                label="Value", help_text="The value stored when this choice is selected"
            ),
        ),
        ("label", CharBlock(label="Label", help_text="The text shown to the user")),
    ],
    label="Choice",
)


class ChoiceSchemaBlock(FieldSchemaBlock):
    """Dropdown selection field (single choice)."""

    choices = ListBlock(
        _ChoiceItemBlock,
        help_text="Add one entry per available choice",
    )
    search_index = BooleanBlock(
        required=False,
        default=True,
        help_text="Index this field content for searching",
    )

    class Meta:
        label = "Choice"
        icon = "list-ul"
        group = "Advanced Fields"


class MultipleChoiceSchemaBlock(FieldSchemaBlock):
    """Multi-select field (multiple choices)."""

    choices = ListBlock(
        _ChoiceItemBlock,
        help_text="Add one entry per available choice",
    )
    search_index = BooleanBlock(
        required=False,
        default=True,
        help_text="Index this field content for searching",
    )

    class Meta:
        label = "Multiple Choice"
        icon = "list-ol"
        group = "Advanced Fields"


# ==============================================================================
# CHOOSER FIELD SCHEMA BLOCKS
# ==============================================================================


class PageChooserSchemaBlock(FieldSchemaBlock):
    """Page link chooser field."""

    page_type = CharBlock(
        required=False,
        max_length=255,
        help_text=(
            "Restrict to specific page types (optional)\\n"
            "Example: blog.BlogPage or app.HomePage"
        ),
    )
    can_choose_root = BooleanBlock(
        required=False,
        default=False,
        help_text="Allow selection of page tree root",
    )

    class Meta:
        label = "Page Chooser"
        icon = "doc-empty-inverse"
        group = "Chooser Fields"


class DocumentChooserSchemaBlock(FieldSchemaBlock):
    """Document chooser field."""

    class Meta:
        label = "Document Chooser"
        icon = "doc-full"
        group = "Chooser Fields"


class ImageChooserSchemaBlock(FieldSchemaBlock):
    """Image chooser field."""

    class Meta:
        label = "Image Chooser"
        icon = "image"
        group = "Chooser Fields"


class ImageSchemaBlock(FieldSchemaBlock):
    """Image field with alt text support."""

    # Note: ImageBlock is different from ImageChooserBlock - includes alt text

    class Meta:
        label = "Image with Alt Text"
        icon = "image"
        group = "Chooser Fields"


class SnippetChooserSchemaBlock(FieldSchemaBlock):
    """Snippet chooser field."""

    target_model = CharBlock(
        max_length=255,
        help_text=(
            "Target snippet model in format: app_label.ModelName\n"
            "Example: blog.Author or products.Category"
        ),
    )

    class Meta:
        label = "Snippet Chooser"
        icon = "snippet"
        group = "Chooser Fields"


class VideoChooserSchemaBlock(FieldSchemaBlock):
    """Video chooser field (requires wagtailmedia)."""

    class Meta:
        label = "Video Chooser"
        icon = "media"
        group = "Chooser Fields"


# ==============================================================================
# EMBED & MEDIA FIELD SCHEMA BLOCKS
# ==============================================================================


class EmbedSchemaBlock(FieldSchemaBlock):
    """Media embed field (video, social media, etc.)."""

    min_length = IntegerBlock(
        required=False,
        min_value=0,
        help_text="Minimum URL length (optional)",
    )
    max_length = IntegerBlock(
        required=False,
        min_value=1,
        help_text="Maximum URL length (optional)",
    )
    max_width = IntegerBlock(
        required=False,
        min_value=1,
        help_text="Maximum embed width in pixels (optional)",
    )
    max_height = IntegerBlock(
        required=False,
        min_value=1,
        help_text="Maximum embed height in pixels (optional)",
    )

    class Meta:
        label = "Embed (Video/Social)"
        icon = "media"
        group = "Embed & Media"


# ==============================================================================
# FIELD BLOCK CHOICES REGISTRY
# ==============================================================================


# streams/blocks/schema.py


class RegistryMeta(type):
    """
    Metaclass that validates uniqueness and provides a .choices property.
    """

    def __new__(mcs, name, bases, attrs):
        # 1. Validation: Ensure no duplicate identifiers (e.g. "char_field")
        seen_identifiers = set()

        for key, value in attrs.items():
            # Check only tuple attributes that don't start with underscore
            if not key.startswith("_") and isinstance(value, tuple):
                identifier = value[0]
                if identifier in seen_identifiers:
                    raise AttributeError(
                        f"Duplicate identifier found in {name}: '{identifier}'. "
                        f"Check the definition of '{key}'."
                    )
                seen_identifiers.add(identifier)

        # 2. Construction: Create the class normally
        return super().__new__(mcs, name, bases, attrs)

    @property
    def choices(cls):
        """
        Dynamically returns a list of all defined field block tuples.
        Filters out internal attributes and the property itself.
        """
        return [
            value
            for key, value in cls.__dict__.items()
            if not key.startswith("_") and key != "choices"
        ]


class FIELD_BLOCK_CHOICES(metaclass=RegistryMeta):
    """
    Centralized registry of all field schema block choices.

    Access via: FIELD_BLOCK_CHOICES.choices
    """

    # Text Fields
    CHAR = ("char_field", CharSchemaBlock())
    TEXT = ("text_field", TextSchemaBlock())
    EMAIL = ("email_field", EmailSchemaBlock())
    URL = ("url_field", URLSchemaBlock())
    BLOCKQUOTE = ("blockquote_field", BlockQuoteSchemaBlock())
    RAW_HTML = ("raw_html_field", RawHTMLSchemaBlock())

    # Numeric Fields
    INTEGER = ("integer_field", IntegerSchemaBlock())
    FLOAT = ("float_field", FloatSchemaBlock())
    DECIMAL = ("decimal_field", DecimalSchemaBlock())

    # Boolean
    BOOLEAN = ("boolean_field", BooleanSchemaBlock())

    # Date/Time
    DATE = ("date_field", DateSchemaBlock())
    TIME = ("time_field", TimeSchemaBlock())
    DATETIME = ("datetime_field", DateTimeSchemaBlock())

    # Rich Content
    RICH_TEXT = ("rich_text_field", RichTextSchemaBlock())

    # Advanced
    REGEX = ("regex_field", RegexSchemaBlock())
    CHOICE = ("choice_field", ChoiceSchemaBlock())
    MULTIPLE_CHOICE = ("multiple_choice_field", MultipleChoiceSchemaBlock())

    # Choosers
    PAGE_CHOOSER = ("page_chooser_field", PageChooserSchemaBlock())
    DOCUMENT_CHOOSER = ("document_chooser_field", DocumentChooserSchemaBlock())
    IMAGE_CHOOSER = ("image_chooser_field", ImageChooserSchemaBlock())
    IMAGE = ("image_field", ImageSchemaBlock())
    SNIPPET_CHOOSER = ("snippet_chooser_field", SnippetChooserSchemaBlock())
    VIDEO_CHOOSER = ("video_chooser_field", VideoChooserSchemaBlock())

    # Embed
    EMBED = ("embed_field", EmbedSchemaBlock())
