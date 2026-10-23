"""
All 25 field schema blocks.

These are meta-blocks used to define the structure of other blocks.
Each corresponds to a Wagtail field block type.

Organized by category:
- Text Fields (6 types)
- Numeric Fields (3 types)
- Boolean (1 type)
- Date/Time (3 types)
- Rich Content (1 type)
- Advanced (3 types)
- Choosers (7 types)
- Embed & Media (1 type)
"""

from django.utils.translation import gettext_lazy as _
from django.utils.translation import pgettext_lazy
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
        help_text=_("Minimum character length (optional)"),
    )
    max_length = IntegerBlock(
        required=False,
        min_value=1,
        help_text=_("Maximum character length (optional)"),
    )
    search_index = BooleanBlock(
        required=False,
        default=True,
        help_text=_("Index this field content for searching"),
    )

    class Meta:
        label = _("Single Line Text (Char)")
        icon = "short-text"
        group = _("Text Fields")


class TextSchemaBlock(FieldSchemaBlock):
    """Multi-line text area field."""

    min_length = IntegerBlock(
        required=False,
        min_value=0,
        help_text=_("Minimum character length (optional)"),
    )
    max_length = IntegerBlock(
        required=False,
        min_value=1,
        help_text=_("Maximum character length (optional)"),
    )
    rows = IntegerBlock(
        required=False,
        min_value=1,
        help_text=_("Number of visible text lines (optional)"),
    )
    search_index = BooleanBlock(
        required=False,
        default=True,
        help_text=_("Index this field content for searching"),
    )

    class Meta:
        label = _("Multi-line Text")
        icon = "subject"
        group = _("Text Fields")


class EmailSchemaBlock(FieldSchemaBlock):
    """Email address field with validation."""

    class Meta:
        label = pgettext_lazy("field type", "Email")
        icon = "mail"
        group = _("Text Fields")


class URLSchemaBlock(FieldSchemaBlock):
    """URL field with validation."""

    min_length = IntegerBlock(
        required=False,
        min_value=0,
        help_text=_("Minimum character length (optional)"),
    )
    max_length = IntegerBlock(
        required=False,
        min_value=1,
        help_text=_("Maximum character length (optional)"),
    )

    class Meta:
        label = pgettext_lazy("field type", "URL")
        icon = "link"
        group = _("Text Fields")


class BlockQuoteSchemaBlock(FieldSchemaBlock):
    """Block quote text field."""

    min_length = IntegerBlock(
        required=False,
        min_value=0,
        help_text=_("Minimum character length (optional)"),
    )
    max_length = IntegerBlock(
        required=False,
        min_value=1,
        help_text=_("Maximum character length (optional)"),
    )

    class Meta:
        label = _("Block Quote")
        icon = "quote"
        group = _("Text Fields")


class RawHTMLSchemaBlock(FieldSchemaBlock):
    """Raw HTML field (unescaped)."""

    min_length = IntegerBlock(
        required=False,
        min_value=0,
        help_text=_("Minimum character length (optional)"),
    )
    max_length = IntegerBlock(
        required=False,
        min_value=1,
        help_text=_("Maximum character length (optional)"),
    )

    class Meta:
        label = _("Raw HTML")
        icon = "code"
        group = _("Text Fields")


# ==============================================================================
# NUMERIC FIELD SCHEMA BLOCKS
# ==============================================================================


class IntegerSchemaBlock(FieldSchemaBlock):
    """Whole number input field."""

    min_value = IntegerBlock(
        required=False,
        help_text=_("Minimum value (optional)"),
    )
    max_value = IntegerBlock(
        required=False,
        help_text=_("Maximum value (optional)"),
    )

    class Meta:
        label = _("Integer")
        icon = "numbers"
        group = _("Numeric Fields")


class FloatSchemaBlock(FieldSchemaBlock):
    """Floating-point number input field."""

    min_value = IntegerBlock(
        required=False,
        help_text=_("Minimum value (optional)"),
    )
    max_value = IntegerBlock(
        required=False,
        help_text=_("Maximum value (optional)"),
    )

    class Meta:
        label = _("Float")
        icon = "numbers"
        group = _("Numeric Fields")


class DecimalSchemaBlock(FieldSchemaBlock):
    """Decimal number field with precision control."""

    min_value = IntegerBlock(
        required=False,
        help_text=_("Minimum value (optional)"),
    )
    max_value = IntegerBlock(
        required=False,
        help_text=_("Maximum value (optional)"),
    )
    max_digits = IntegerBlock(
        required=False,
        min_value=1,
        help_text=_("Total number of digits (optional)"),
    )
    decimal_places = IntegerBlock(
        required=False,
        min_value=0,
        help_text=_("Number of decimal places (optional)"),
    )

    class Meta:
        label = _("Decimal")
        icon = "numbers"
        group = _("Numeric Fields")


# ==============================================================================
# BOOLEAN FIELD SCHEMA BLOCKS
# ==============================================================================


class BooleanSchemaBlock(FieldSchemaBlock):
    """Checkbox field for true/false values."""

    # Note: BooleanBlock in Wagtail doesn't use 'required' parameter
    # It's always optional (checkbox unchecked = False)

    class Meta:
        label = _("Boolean (Checkbox)")
        icon = "check-box"
        group = _("Boolean & Logic")


# ==============================================================================
# DATE/TIME FIELD SCHEMA BLOCKS
# ==============================================================================


class DateSchemaBlock(FieldSchemaBlock):
    """Date picker field."""

    format = CharBlock(
        required=False,
        max_length=50,
        help_text=_("Date format (from Django's DATE_INPUT_FORMATS, optional)"),
    )

    class Meta:
        label = _("Date")
        icon = "calendar-today"
        group = _("Date & Time")


class TimeSchemaBlock(FieldSchemaBlock):
    """Time picker field."""

    format = CharBlock(
        required=False,
        max_length=50,
        help_text=_("Time format (from Django's TIME_INPUT_FORMATS, optional)"),
    )

    class Meta:
        label = _("Time")
        icon = "schedule"
        group = _("Date & Time")


class DateTimeSchemaBlock(FieldSchemaBlock):
    """Combined date and time picker field."""

    format = CharBlock(
        required=False,
        max_length=50,
        help_text=_("DateTime format (from Django's DATETIME_INPUT_FORMATS, optional)"),
    )

    class Meta:
        label = _("Date & Time")
        icon = "calendar-clock"
        group = _("Date & Time")


# ==============================================================================
# RICH CONTENT FIELD SCHEMA BLOCKS
# ==============================================================================


class RichTextSchemaBlock(FieldSchemaBlock):
    """WYSIWYG rich text editor field."""

    min_length = IntegerBlock(
        required=False,
        min_value=0,
        help_text=_("Minimum character length (text-only, optional)"),
    )
    max_length = IntegerBlock(
        required=False,
        min_value=1,
        help_text=_("Maximum character length (text-only, optional)"),
    )
    search_index = BooleanBlock(
        required=False,
        default=True,
        help_text=_("Index this field content for searching"),
    )
    editor = CharBlock(
        required=False,
        max_length=100,
        help_text=_("Rich text editor selection (optional)"),
    )
    features = MultipleChoiceBlock(
        required=False,
        choices=[
            ("h1", _("Heading 1")),
            ("h2", _("Heading 2")),
            ("h3", _("Heading 3")),
            ("h4", _("Heading 4")),
            ("h5", _("Heading 5")),
            ("h6", _("Heading 6")),
            ("bold", _("Bold")),
            ("italic", _("Italic")),
            ("underline", _("Underline")),
            ("strikethrough", _("Strikethrough")),
            ("ol", _("Ordered List")),
            ("ul", _("Unordered List")),
            ("link", _("Link")),
            ("document-link", _("Document Link")),
            ("blockquote", _("Block Quote")),
            ("superscript", _("Superscript")),
            ("subscript", _("Subscript")),
            ("code", pgettext_lazy("source code", "Code")),
            ("hr", _("Horizontal Rule")),
            ("embed", _("Embed")),
            ("image", _("Image")),
        ],
        help_text=_("Select which formatting features should be available in the editor"),
    )

    class Meta:
        label = _("Rich Text Editor")
        icon = "format-paragraph"
        group = _("Rich Content")


# ==============================================================================
# REGEX FIELD SCHEMA BLOCKS
# ==============================================================================


class RegexSchemaBlock(FieldSchemaBlock):
    """Text field with custom regex validation."""

    regex = CharBlock(
        max_length=500,
        help_text=_("Regular expression pattern to validate against"),
    )
    min_length = IntegerBlock(
        required=False,
        min_value=0,
        help_text=_("Minimum character length (optional)"),
    )
    max_length = IntegerBlock(
        required=False,
        min_value=1,
        help_text=_("Maximum character length (optional)"),
    )
    error_messages = TextBlock(
        required=False,
        help_text=(
            _(
                "Error messages in JSON format (optional)\\n"
                '{"required": "This field is required", "invalid": "Invalid format"}'
            )
        ),
    )

    class Meta:
        label = _("Regular Expression")
        icon = "regular-expression"
        group = _("Advanced Fields")


# ==============================================================================
# CHOICE FIELD SCHEMA BLOCKS
# ==============================================================================


_ChoiceItemBlock = StructBlock(
    [
        (
            "value",
            CharBlock(label=_("Value"), help_text=_("The value stored when this choice is selected")),
        ),
        ("label", CharBlock(label=_("Label"), help_text=_("The text shown to the user"))),
    ],
    label=_("Choice"),
)


class ChoiceSchemaBlock(FieldSchemaBlock):
    """Dropdown selection field (single choice)."""

    choices = ListBlock(
        _ChoiceItemBlock,
        help_text=_("Add one entry per available choice"),
    )
    search_index = BooleanBlock(
        required=False,
        default=True,
        help_text=_("Index this field content for searching"),
    )

    class Meta:
        label = _("Choice")
        icon = "radio-button-checked"
        group = _("Advanced Fields")


class MultipleChoiceSchemaBlock(FieldSchemaBlock):
    """Multi-select field (multiple choices)."""

    choices = ListBlock(
        _ChoiceItemBlock,
        help_text=_("Add one entry per available choice"),
    )
    search_index = BooleanBlock(
        required=False,
        default=True,
        help_text=_("Index this field content for searching"),
    )

    class Meta:
        label = _("Multiple Choice")
        icon = "checklist"
        group = _("Advanced Fields")


# ==============================================================================
# CHOOSER FIELD SCHEMA BLOCKS
# ==============================================================================


class PageChooserSchemaBlock(FieldSchemaBlock):
    """Page link chooser field."""

    page_type = CharBlock(
        required=False,
        max_length=255,
        help_text=_("Restrict to specific page types (optional)\\nExample: blog.BlogPage or app.HomePage"),
    )
    can_choose_root = BooleanBlock(
        required=False,
        default=False,
        help_text=_("Allow selection of page tree root"),
    )

    class Meta:
        label = _("Page Chooser")
        icon = "draft"
        group = _("Chooser Fields")


class DocumentChooserSchemaBlock(FieldSchemaBlock):
    """Document chooser field."""

    class Meta:
        label = _("Document Chooser")
        icon = "description"
        group = _("Chooser Fields")


class ImageChooserSchemaBlock(FieldSchemaBlock):
    """Image chooser field."""

    class Meta:
        label = _("Image Chooser")
        icon = "image"
        group = _("Chooser Fields")


class ImageSchemaBlock(FieldSchemaBlock):
    """Image field with alt text support."""

    # Note: ImageBlock is different from ImageChooserBlock - includes alt text

    class Meta:
        label = _("Image with Alt Text")
        icon = "image"
        group = _("Chooser Fields")


class SnippetChooserSchemaBlock(FieldSchemaBlock):
    """Snippet chooser field."""

    target_model = CharBlock(
        max_length=255,
        help_text=_("Target snippet model in format: app_label.ModelName\nExample: blog.Author or products.Category"),
    )

    class Meta:
        label = _("Snippet Chooser")
        icon = "snippet"
        group = _("Chooser Fields")


class VideoChooserSchemaBlock(FieldSchemaBlock):
    """Video chooser field (requires wagtailmedia)."""

    class Meta:
        label = _("Video Chooser")
        icon = "media"
        group = _("Chooser Fields")


class AudioChooserSchemaBlock(FieldSchemaBlock):
    """Audio chooser field (requires wagtailmedia)."""

    class Meta:
        label = _("Audio Chooser")
        icon = "media"
        group = _("Chooser Fields")


# ==============================================================================
# EMBED & MEDIA FIELD SCHEMA BLOCKS
# ==============================================================================


class EmbedSchemaBlock(FieldSchemaBlock):
    """Media embed field (video, social media, etc.)."""

    min_length = IntegerBlock(
        required=False,
        min_value=0,
        help_text=_("Minimum URL length (optional)"),
    )
    max_length = IntegerBlock(
        required=False,
        min_value=1,
        help_text=_("Maximum URL length (optional)"),
    )
    max_width = IntegerBlock(
        required=False,
        min_value=1,
        help_text=_("Maximum embed width in pixels (optional)"),
    )
    max_height = IntegerBlock(
        required=False,
        min_value=1,
        help_text=_("Maximum embed height in pixels (optional)"),
    )

    class Meta:
        label = _("Embed (Video/Social)")
        icon = "media"
        group = _("Embed & Media")


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
                        f"Duplicate identifier found in {name}: '{identifier}'. Check the definition of '{key}'."
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
        return [value for key, value in cls.__dict__.items() if not key.startswith("_") and key != "choices"]


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
    AUDIO_CHOOSER = ("audio_chooser_field", AudioChooserSchemaBlock())

    # Embed
    EMBED = ("embed_field", EmbedSchemaBlock())
