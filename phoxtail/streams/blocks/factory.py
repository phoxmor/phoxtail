"""
Factory for generating Wagtail blocks dynamically from database-stored schemas.

This module reads Block.schema and creates actual Wagtail block classes at runtime.
"""

from wagtail.blocks import (
    BooleanBlock,
    CharBlock,
    ChoiceBlock,
    DateBlock,
    DateTimeBlock,
    EmailBlock,
    FloatBlock,
    IntegerBlock,
    ListBlock,
    MultipleChoiceBlock,
    PageChooserBlock,
    RawHTMLBlock,
    RegexBlock,
    RichTextBlock,
    StreamBlock,
    StructBlock,
    TextBlock,
    TimeBlock,
    URLBlock,
)
from wagtail.documents.blocks import DocumentChooserBlock
from wagtail.embeds.blocks import EmbedBlock
from wagtail.images.blocks import ImageChooserBlock
from wagtail.snippets.blocks import SnippetChooserBlock
from wagtailmedia.blocks import AudioChooserBlock, VideoChooserBlock

from .base import BlockVariantStructBlock

# ---------------------------------------------------------------------------
# Shared block generation modes
# ---------------------------------------------------------------------------
#
# Mode 1 (normal):      create_block_from_schema     — all fields + variant
# Mode 2 (shared ref):  create_shared_block_ref      — variant only
# Mode 3 (shared edit): create_shared_block_from_schema  — all fields, no variant
# ---------------------------------------------------------------------------


def create_block_from_schema(block):
    """
    Reads a Block instance's schema and generates a Wagtail block class.

    Args:
        block: A Block model instance with a schema StreamField

    Returns:
        An instance of a dynamically-generated StructBlock

    Example:
        block = Block.objects.get(identifier='header_section')
        block_instance = create_block_from_schema(block)
        # Now block_instance can be used in a StreamField
    """
    fields = {}

    for item in block.schema:
        block_type = item.block_type
        field_name = item.value.get("name", "unnamed")

        # Use recursive helper to create any type of block
        created_block = _create_any_block(block_type, item.value)
        if created_block:
            fields[field_name] = created_block

    # Store the identifier so render() can look up the Block instance
    fields["_block_identifier"] = block.identifier

    # Add variant field with filtering by block identifier
    # This ensures only variants designed for this specific block type are shown
    from phoxtail.streams.views import BlockVariantChooserBlock

    fields["variant"] = BlockVariantChooserBlock(
        block_identifier=block.identifier,
        required=False,
    )

    # Create Meta class with icon, label, and optional group
    meta_attrs = {"icon": block.icon if block.icon else "placeholder"}
    if block.name:
        meta_attrs["label"] = block.name
    if block.group:
        meta_attrs["group"] = block.group

    # Always add Meta class with at least the icon
    Meta = type("Meta", (), meta_attrs)
    fields["Meta"] = Meta

    # Create the main StructBlock class with variant support
    BlockClass = type(
        f"{_to_class_name(block.identifier)}Block",
        (BlockVariantStructBlock,),
        fields,
    )

    return BlockClass()


def create_shared_block_ref(block):
    """
    Mode 2: Creates a lightweight block for page StreamFields.

    Only contains a variant chooser — no content fields. Content is fetched
    from SharedBlock at render time.

    Args:
        block: A Block model instance with is_shared=True

    Returns:
        An instance of a dynamically-generated StructBlock with only variant chooser
    """
    fields = {}

    # Store metadata (removed from child_blocks in __init__)
    fields["_block_identifier"] = block.identifier
    fields["_is_shared"] = True

    # Only a variant chooser — no content fields
    from phoxtail.streams.views import BlockVariantChooserBlock

    fields["variant"] = BlockVariantChooserBlock(
        block_identifier=block.identifier,
        required=False,
    )

    # Create Meta class with icon, label, and group
    meta_attrs = {
        "icon": block.icon if block.icon else "placeholder",
        "group": "Shared",
    }
    if block.name:
        meta_attrs["label"] = block.name

    Meta = type("Meta", (), meta_attrs)
    fields["Meta"] = Meta

    BlockClass = type(
        f"{_to_class_name(block.identifier)}Block",
        (BlockVariantStructBlock,),
        fields,
    )

    return BlockClass()


def create_shared_block_from_schema(block):
    """
    Mode 3: Creates a full content block for SharedBlock editing.

    Contains all content fields from the schema but NO variant chooser.
    Uses plain StructBlock (no variant rendering logic needed).

    Args:
        block: A Block model instance with is_shared=True

    Returns:
        An instance of a dynamically-generated StructBlock with all content fields
    """
    fields = {}

    for item in block.schema:
        block_type = item.block_type
        field_name = item.value.get("name", "unnamed")

        created_block = _create_any_block(block_type, item.value)
        if created_block:
            fields[field_name] = created_block

    # No _block_identifier (not needed for content editing)
    # No variant (variants are chosen per-page, not here)

    # Create Meta class with icon and label
    meta_attrs = {"icon": block.icon if block.icon else "placeholder"}
    if block.name:
        meta_attrs["label"] = block.name

    Meta = type("Meta", (), meta_attrs)
    fields["Meta"] = Meta

    # Plain StructBlock — this is just a data entry form
    BlockClass = type(
        f"{_to_class_name(block.identifier)}ContentBlock",
        (StructBlock,),
        fields,
    )

    return BlockClass()


def _create_any_block(block_type, block_value):
    """
    Recursively creates any type of block (field, struct, or list).

    Args:
        block_type: The block type string (e.g., "char_field", "struct", "list_struct")
        block_value: Dictionary with block configuration

    Returns:
        An instance of the appropriate Wagtail block type
    """
    # Handle list of simple fields (check before endswith("_field") since
    # "list_field" matches that pattern but is a structure, not a field)
    if block_type == "list_field":
        # Extract the single block definition (schema enforces min_num=1, max_num=1)
        blocks = block_value.get("blocks", [])

        if not blocks or len(blocks) == 0:
            # No block defined - fallback to default CharBlock
            print("Warning: ListFieldSchemaBlock has no blocks defined")
            child_block = CharBlock(required=True)
        else:
            # Get the first (and only) block with its full configuration
            field_schema = blocks[0]
            field_block_type = field_schema.block_type
            field_config = field_schema.value

            # Create the child block using the schema configuration
            # This now respects max_length, help_text,
            # and other field-specific parameters
            child_block = _create_any_block(field_block_type, field_config)

        if not child_block:
            # Fallback if creation failed
            child_block = CharBlock(required=True)

        # Build ListBlock with common parameters, constraints, and UI configuration
        list_kwargs = {}
        if block_value.get("required") is not None:
            list_kwargs["required"] = block_value["required"]
        if block_value.get("help_text"):
            list_kwargs["help_text"] = block_value["help_text"]
        if block_value.get("min_num") is not None:
            list_kwargs["min_num"] = block_value["min_num"]
        if block_value.get("max_num") is not None:
            list_kwargs["max_num"] = block_value["max_num"]
        if block_value.get("collapsed") is not None:
            list_kwargs["collapsed"] = block_value["collapsed"]

        return ListBlock(child_block, **list_kwargs)

    # Handle field schema blocks
    elif block_type.endswith("_field"):
        return _create_field_block(block_type, block_value)

    # Handle nested structure
    elif block_type == "struct":
        struct_fields = {}

        # Recursively process blocks inside the nested structure
        for nested_item in block_value.get("blocks", []):
            nested_block_type = nested_item.block_type
            nested_name = nested_item.value.get("name", "unnamed")
            nested_block = _create_any_block(nested_block_type, nested_item.value)
            if nested_block:
                struct_fields[nested_name] = nested_block

        # Create Meta class with icon (defaults to placeholder if not provided)
        meta_attrs = {"icon": block_value.get("icon") or "placeholder"}
        Meta = type("Meta", (), meta_attrs)
        struct_fields["Meta"] = Meta

        # Dynamically create a StructBlock class for this nested structure
        struct_name = block_value.get("name", "UnnamedStruct")
        NestedBlockClass = type(
            f"{_to_class_name(struct_name)}Block",
            (StructBlock,),
            struct_fields,
        )

        # Build StructBlock with common parameters and UI configuration
        struct_kwargs = {}
        if block_value.get("required") is not None:
            struct_kwargs["required"] = block_value["required"]
        if block_value.get("help_text"):
            struct_kwargs["help_text"] = block_value["help_text"]
        if block_value.get("collapsed") is not None:
            struct_kwargs["collapsed"] = block_value["collapsed"]

        return NestedBlockClass(**struct_kwargs)

    # Handle list of structured items
    elif block_type == "list_struct":
        struct_fields = {}

        # Recursively build the struct fields for each list item
        for field_item in block_value.get("blocks", []):
            field_block_type = field_item.block_type
            field_name = field_item.value.get("name", "unnamed")
            field_block = _create_any_block(field_block_type, field_item.value)
            if field_block:
                struct_fields[field_name] = field_block

        # Create Meta class with icon (defaults to placeholder if not provided)
        meta_attrs = {"icon": block_value.get("icon") or "placeholder"}
        Meta = type("Meta", (), meta_attrs)
        struct_fields["Meta"] = Meta

        # Create StructBlock class for list items
        list_name = block_value.get("name", "UnnamedList")
        ListItemClass = type(
            f"{_to_class_name(list_name)}ItemBlock",
            (StructBlock,),
            struct_fields,
        )

        # Build ListBlock with common parameters, constraints, and UI configuration
        list_kwargs = {}
        if block_value.get("required") is not None:
            list_kwargs["required"] = block_value["required"]
        if block_value.get("help_text"):
            list_kwargs["help_text"] = block_value["help_text"]
        if block_value.get("min_num") is not None:
            list_kwargs["min_num"] = block_value["min_num"]
        if block_value.get("max_num") is not None:
            list_kwargs["max_num"] = block_value["max_num"]
        if block_value.get("collapsed") is not None:
            list_kwargs["collapsed"] = block_value["collapsed"]

        return ListBlock(ListItemClass(), **list_kwargs)

    # Handle stream of mixed content
    elif block_type == "stream":
        stream_blocks = []

        # Recursively build each allowed block type in the stream
        for stream_item in block_value.get("blocks", []):
            stream_block_type = stream_item.block_type
            stream_block_name = stream_item.value.get("name", "unnamed")
            stream_block = _create_any_block(stream_block_type, stream_item.value)
            if stream_block:
                stream_blocks.append((stream_block_name, stream_block))

        # Build StreamBlock with common parameters and constraints
        stream_kwargs = {}
        if block_value.get("required") is not None:
            stream_kwargs["required"] = block_value["required"]
        if block_value.get("help_text"):
            stream_kwargs["help_text"] = block_value["help_text"]
        if block_value.get("min_num") is not None:
            stream_kwargs["min_num"] = block_value["min_num"]
        if block_value.get("max_num") is not None:
            stream_kwargs["max_num"] = block_value["max_num"]
        if block_value.get("collapsed") is not None:
            stream_kwargs["collapsed"] = block_value["collapsed"]
        if block_value.get("search_index") is not None:
            stream_kwargs["search_index"] = block_value["search_index"]

        # Handle block_counts (per-block-type limits)
        if block_value.get("block_counts"):
            import json

            try:
                block_counts_data = json.loads(block_value["block_counts"])
                stream_kwargs["block_counts"] = block_counts_data
            except (json.JSONDecodeError, TypeError):
                # Invalid JSON - skip block_counts
                pass

        return StreamBlock(stream_blocks, **stream_kwargs)

    return None


def _create_field_block(block_type, field_def):
    """
    Maps a field schema block_type to an actual Wagtail block instance.

    Args:
        block_type: The block type string (e.g., "char_field", "email_field")
        field_def: Dictionary with field configuration from the schema

    Returns:
        An instance of the appropriate Wagtail block type
    """
    # Extract common parameters
    required = field_def.get("required", True)
    help_text = field_def.get("help_text", "")
    icon = field_def.get("icon", "")

    # Build base kwargs
    kwargs = {"required": required}
    if help_text:
        kwargs["help_text"] = help_text
    if icon:
        kwargs["icon"] = icon

    # Direct mapping: block_type → (WagtailBlock, [param_names])
    block_map = {
        # Text Fields
        "char_field": (CharBlock, ["max_length"]),
        "text_field": (TextBlock, ["rows"]),
        "email_field": (EmailBlock, ["max_length"]),
        "url_field": (URLBlock, ["max_length"]),
        "blockquote_field": (TextBlock, []),  # BlockQuoteBlock is just TextBlock
        "raw_html_field": (RawHTMLBlock, ["max_length"]),
        # Numeric Fields
        "integer_field": (IntegerBlock, ["min_value", "max_value"]),
        "float_field": (FloatBlock, ["min_value", "max_value"]),
        "decimal_field": (
            FloatBlock,
            ["min_value", "max_value", "max_digits", "decimal_places"],
        ),  # Using FloatBlock for now
        # Boolean
        "boolean_field": (
            BooleanBlock,
            [],
        ),  # Note: BooleanBlock doesn't use 'required'
        # Date/Time
        "date_field": (DateBlock, []),
        "time_field": (TimeBlock, []),
        "datetime_field": (DateTimeBlock, []),
        # Rich Content
        "rich_text_field": (RichTextBlock, ["features", "editor"]),
        # Advanced
        "regex_field": (RegexBlock, ["regex", "error_message", "max_length"]),
        "choice_field": (ChoiceBlock, ["choices"]),
        "multiple_choice_field": (MultipleChoiceBlock, ["choices"]),
        # Choosers
        "page_chooser_field": (PageChooserBlock, ["page_type", "can_choose_root"]),
        "document_chooser_field": (DocumentChooserBlock, []),
        "image_chooser_field": (ImageChooserBlock, []),
        "image_field": (ImageChooserBlock, []),  # Using ImageChooserBlock for now
        "snippet_chooser_field": (SnippetChooserBlock, ["target_model"]),
        "video_chooser_field": (VideoChooserBlock, []),
        "audio_chooser_field": (AudioChooserBlock, []),
        # Embed
        "embed_field": (EmbedBlock, []),
    }

    if block_type not in block_map:
        # Fallback for unknown types
        print(f"Warning: Unknown block type '{block_type}', defaulting to CharBlock")
        return CharBlock(**kwargs)

    BlockClass, param_names = block_map[block_type]

    # Add type-specific parameters
    for param_name in param_names:
        if param_name in field_def and field_def[param_name]:
            value = field_def[param_name]

            # Special handling for choices (convert from text format)
            if param_name == "choices":
                kwargs["choices"] = _parse_choices(value)
            # Special handling for features (convert to list if needed)
            elif param_name == "features":
                # MultipleChoiceBlock already returns a list,
                # but handle text format for backward compat
                if isinstance(value, list):
                    kwargs["features"] = value
                elif isinstance(value, str):
                    kwargs["features"] = [
                        f.strip() for f in value.strip().split("\n") if f.strip()
                    ]
                else:
                    kwargs["features"] = []
            # Special handling for regex (required parameter)
            elif param_name == "regex":
                # RegexBlock requires regex as first positional argument
                # We'll handle this differently
                pass
            # Special handling for target_model (for SnippetChooserBlock)
            elif param_name == "target_model":
                # SnippetChooserBlock needs the model as first argument
                # We'll handle this differently
                pass
            else:
                kwargs[param_name] = value

    # Special case handling for blocks with required positional arguments
    if block_type == "regex_field" and "regex" in field_def:
        # RegexBlock(regex, **kwargs)
        return RegexBlock(field_def["regex"], **kwargs)

    if block_type == "snippet_chooser_field" and "target_model" in field_def:
        # SnippetChooserBlock(target_model, **kwargs)
        return SnippetChooserBlock(field_def["target_model"], **kwargs)

    return BlockClass(**kwargs)


def _parse_choices(choices_data):
    """
    Convert choices from ListBlock format to tuple format for Wagtail's ChoiceBlock.

    Input: ListValue of StructValues, each with 'value' and 'label' keys
    Output: [("phone", "Phone"), ("mobile", "Mobile"), ...]
    """
    return [
        (str(item["value"]), str(item["label"]))
        for item in choices_data
        if item.get("value")
    ]


def _to_class_name(snake_case_name):
    """
    Converts snake_case to PascalCase for class names.

    Examples:
        'header_section' -> 'HeaderSection'
        'text' -> 'Text'
    """
    return "".join(word.capitalize() for word in snake_case_name.split("_"))


def get_dynamic_blocks():
    """
    Returns cached block tuples for all Block instances in the database.

    This is designed to be used as a callable in StreamField definitions:
        body = StreamField(get_dynamic_blocks, ...)

    Uses the in-memory cache to avoid regenerating Python classes via type()
    on every call. Cache is invalidated when a Block is saved or deleted.

    Returns:
        List of tuples: [(identifier, block_instance), ...]
    """
    from phoxtail.streams.cache import get_cached_dynamic_blocks

    return get_cached_dynamic_blocks()


def build_dynamic_blocks():
    """
    Generates block tuples for unrestricted Block instances only.

    Only returns blocks with no page_types set (available on all pages).
    Page-type-specific blocks are excluded — use build_blocks_for_page_type()
    to include them for a specific page type.

    Normal blocks use Mode 1 (full content + variant).
    Shared blocks use Mode 2 (variant only — content comes from SharedBlock).

    This is the actual generation logic — called by the cache layer on
    first access or after invalidation. Should not be called directly;
    use get_dynamic_blocks() instead.

    Returns:
        List of tuples: [(identifier, block_instance), ...]
    """
    import logging

    from django.db import ProgrammingError
    from django.db.models import Exists, OuterRef

    from phoxtail.streams.models import Block

    logger = logging.getLogger(__name__)
    blocks = []

    try:
        PageTypeRelation = Block.page_types.through
        no_restriction = ~Exists(
            PageTypeRelation.objects.filter(block_id=OuterRef("pk"))
        )
        for block_def in Block.objects.filter(no_restriction):
            try:
                if block_def.is_shared:
                    block_instance = create_shared_block_ref(block_def)
                else:
                    block_instance = create_block_from_schema(block_def)
                blocks.append((block_def.identifier, block_instance))
            except Exception as e:
                logger.warning("Error creating block '%s': %s", block_def.identifier, e)
                continue
    except (ProgrammingError, Exception):
        # Table doesn't exist yet (before migrations) or schema field is missing
        pass

    return blocks


def build_blocks_for_page_type(content_type_id):
    """
    Generates block tuples for a specific page type.

    Returns unrestricted blocks (no page_types set) PLUS blocks that
    explicitly include the given content_type_id in their page_types.

    Args:
        content_type_id: The primary key of the ContentType to filter by.

    Returns:
        List of tuples: [(identifier, block_instance), ...]
    """
    import logging

    from django.db import ProgrammingError
    from django.db.models import Exists, OuterRef

    from phoxtail.streams.models import Block

    logger = logging.getLogger(__name__)
    blocks = []

    try:
        PageTypeRelation = Block.page_types.through
        no_restriction = ~Exists(
            PageTypeRelation.objects.filter(block_id=OuterRef("pk"))
        )
        has_this_type = Exists(
            PageTypeRelation.objects.filter(
                block_id=OuterRef("pk"), contenttype_id=content_type_id
            )
        )
        for block_def in Block.objects.filter(no_restriction | has_this_type):
            try:
                if block_def.is_shared:
                    block_instance = create_shared_block_ref(block_def)
                else:
                    block_instance = create_block_from_schema(block_def)
                blocks.append((block_def.identifier, block_instance))
            except Exception as e:
                logger.warning("Error creating block '%s': %s", block_def.identifier, e)
                continue
    except (ProgrammingError, Exception):
        # Table doesn't exist yet (before migrations) or schema field is missing
        pass

    return blocks


def build_shared_blocks():
    """
    Generates block tuples for shared Block instances only (Mode 3).

    Returns blocks with full content fields and no variant chooser,
    intended for SharedBlock editing.

    Returns:
        List of tuples: [(identifier, block_instance), ...]
    """
    import logging

    from django.db import ProgrammingError

    from phoxtail.streams.models import Block

    logger = logging.getLogger(__name__)
    blocks = []

    try:
        for block_def in Block.objects.filter(is_shared=True):
            try:
                block_instance = create_shared_block_from_schema(block_def)
                blocks.append((block_def.identifier, block_instance))
            except Exception as e:
                logger.warning(
                    "Error creating shared block '%s': %s",
                    block_def.identifier,
                    e,
                )
                continue
    except (ProgrammingError, Exception):
        # Table doesn't exist yet (before migrations) or schema field is missing
        pass

    return blocks
