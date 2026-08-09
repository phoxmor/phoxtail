from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _
from modelcluster.fields import ParentalKey
from modelcluster.models import ClusterableModel
from wagtail.admin.panels import FieldPanel
from wagtail.fields import StreamField
from wagtail.models import Orderable
from wagtail.search import index

from phoxtail.core.mixins import AdminURLMixin, TimestampMixin, UUIDMixin
from phoxtail.streams.blocks.schema import (
    AudioChooserSchemaBlock,
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
    ListFieldSchemaBlock,
    ListStructSchemaBlock,
    MultipleChoiceSchemaBlock,
    PageChooserSchemaBlock,
    RawHTMLSchemaBlock,
    RegexSchemaBlock,
    RichTextSchemaBlock,
    SnippetChooserSchemaBlock,
    StreamSchemaBlock,
    StructSchemaBlock,
    TextSchemaBlock,
    TimeSchemaBlock,
    URLSchemaBlock,
    VideoChooserSchemaBlock,
)
from phoxtail.streams.fields import SharedBlockStreamField
from phoxtail.streams.utils import _page_content_type_choices


class BlockCategory(UUIDMixin, TimestampMixin, AdminURLMixin, Orderable, index.Indexed):
    name = models.CharField(max_length=100, verbose_name=_("Name"))
    slug = models.SlugField(max_length=100, unique=True, verbose_name=_("Slug"))
    description = models.TextField(blank=True, verbose_name=_("Description"))

    panels = [
        FieldPanel("name"),
        FieldPanel("slug"),
        FieldPanel("description"),
    ]

    search_fields = [
        index.AutocompleteField("name"),
        index.SearchField("description"),
    ]

    class Meta(Orderable.Meta):
        verbose_name = _("Block Category")
        verbose_name_plural = _("Block Categories")

    def __str__(self):
        return self.name


class Block(index.Indexed, Orderable, ClusterableModel):
    """Defines a StreamField block type that can have multiple template variations"""

    name = models.CharField(max_length=255, unique=True, help_text=_("Display name"))
    identifier = models.CharField(
        max_length=100,
        unique=True,
        help_text=_("Unique identifier (e.g., 'header_section', 'simple_hero')"),
    )
    description = models.TextField(
        help_text=_("Description of this block's purpose and use case"),
    )
    icon = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text=_(
            "Wagtail icon name for this block (e.g., 'image', 'doc-full', 'media'). Displayed in the block chooser."
        ),
    )
    group = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text=_("Group label shown in the block chooser (e.g., 'Blog', 'Media'). Leave empty for no grouping."),
    )
    is_shared = models.BooleanField(
        default=False,
        help_text=_(
            "If checked, this block's content is defined once per site/locale "
            "(in Shared Blocks) and shared across pages. "
            "In page editors, only the variant chooser will be shown."
        ),
    )
    source_app = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text=_(
            "Django app label that owns this block (e.g. 'phoxtail_blog'). "
            "Set automatically by populate_streams. Blank means no app dependency — "
            "the block is available in any project."
        ),
    )
    page_types = models.ManyToManyField(
        "contenttypes.ContentType",
        blank=True,
        related_name="+",
        verbose_name=_("Page Types"),
        limit_choices_to=_page_content_type_choices,
        help_text=_("Restrict this block to specific page types. Leave empty to make it available on all pages."),
    )
    categories = models.ManyToManyField(
        "phoxtail_streams.BlockCategory",
        blank=True,
        related_name="blocks",
        verbose_name=_("Categories"),
        help_text=_("Broad purpose groupings (e.g. Marketing, Ecommerce). Keep the vocabulary small and governed."),
    )
    schema = StreamField(
        [
            # Text Fields
            ("char_field", CharSchemaBlock()),
            ("text_field", TextSchemaBlock()),
            ("email_field", EmailSchemaBlock()),
            ("url_field", URLSchemaBlock()),
            ("blockquote_field", BlockQuoteSchemaBlock()),
            ("raw_html_field", RawHTMLSchemaBlock()),
            # Numeric Fields
            ("integer_field", IntegerSchemaBlock()),
            ("float_field", FloatSchemaBlock()),
            ("decimal_field", DecimalSchemaBlock()),
            # Boolean
            ("boolean_field", BooleanSchemaBlock()),
            # Date/Time
            ("date_field", DateSchemaBlock()),
            ("time_field", TimeSchemaBlock()),
            ("datetime_field", DateTimeSchemaBlock()),
            # Rich Content
            ("rich_text_field", RichTextSchemaBlock()),
            # Advanced
            ("regex_field", RegexSchemaBlock()),
            ("choice_field", ChoiceSchemaBlock()),
            ("multiple_choice_field", MultipleChoiceSchemaBlock()),
            # Choosers
            ("page_chooser_field", PageChooserSchemaBlock()),
            ("document_chooser_field", DocumentChooserSchemaBlock()),
            ("image_chooser_field", ImageChooserSchemaBlock()),
            ("image_field", ImageSchemaBlock()),
            ("snippet_chooser_field", SnippetChooserSchemaBlock()),
            ("video_chooser_field", VideoChooserSchemaBlock()),
            ("audio_chooser_field", AudioChooserSchemaBlock()),
            # Embed
            ("embed_field", EmbedSchemaBlock()),
            # Structures
            ("struct", StructSchemaBlock()),
            ("list_field", ListFieldSchemaBlock()),
            ("list_struct", ListStructSchemaBlock()),
            ("stream", StreamSchemaBlock()),
        ],
        use_json_field=True,
        blank=True,
        help_text=_(
            "Define the structure of this block using field schema blocks, nested structures, lists, and streams"
        ),
        collapsed=True,
    )
    search_fields = [
        index.AutocompleteField("name"),
        index.AutocompleteField("identifier"),
        index.SearchField("name"),
        index.SearchField("identifier"),
        index.SearchField("description"),
        index.FilterField("is_shared"),
    ]

    class Meta(Orderable.Meta):
        verbose_name = _("Block")
        verbose_name_plural = _("Blocks")

    def __str__(self):
        return self.name

    @property
    def default_variant(self):
        return self.variants.filter(is_default=True).first()


class VariantCollection(index.Indexed, ClusterableModel):
    """Collection of BlockVariant instances sharing common design principles"""

    name = models.CharField(
        max_length=255,
        unique=True,
        help_text=_("Collection name (e.g., 'Material Design', 'Minimalist')"),
    )
    identifier = models.CharField(
        max_length=100,
        unique=True,
        help_text=_("Unique identifier (e.g., 'material_design_3')"),
    )
    description = models.TextField(
        help_text=_("Short description of this collection's purpose"),
    )
    search_fields = [
        index.AutocompleteField("name"),
        index.AutocompleteField("identifier"),
        index.SearchField("name"),
        index.SearchField("identifier"),
        index.SearchField("description"),
        index.FilterField("id"),
    ]

    class Meta:
        verbose_name = _("Collection")
        verbose_name_plural = _("Collections")
        ordering = ["name"]

    def __str__(self):
        return self.name


class BlockVariant(index.Indexed, models.Model):
    """Variant for a specific Block within a Collection"""

    block = ParentalKey(Block, on_delete=models.CASCADE, related_name="variants")
    collection = models.ForeignKey(
        VariantCollection,
        on_delete=models.SET_NULL,
        related_name="variants",
        null=True,
        blank=True,
        help_text=_("Optional design-system label for this variant (e.g. 'Material Design 3')."),
    )
    name = models.CharField(
        max_length=255,
        help_text=_("Variant name for identification (e.g., 'Centered', 'With Background')"),
    )
    identifier = models.CharField(
        max_length=100,
        help_text=_("Identifier for this variant (e.g., 'centered_dark', 'split_layout')"),
    )
    description = models.TextField(
        help_text=_("Design rationale and approach. Explain why this variant exists and what makes it different."),
    )
    is_default = models.BooleanField(
        default=False,
        help_text=_("Whether this is the default variant for its block. Only one default per block."),
    )

    # Template fields (split from single 'code' field)
    html = models.TextField(
        default="",
        help_text=_("HTML template with DTL/Jinja2 tags."),
    )
    css = models.TextField(
        blank=True,
        default="",
        help_text=_("CSS styles for this variant."),
    )
    javascript = models.TextField(
        blank=True,
        default="",
        help_text=_("JavaScript code for this variant."),
    )
    preview_image_desktop = models.ForeignKey(
        settings.WAGTAILIMAGES_IMAGE_MODEL,
        on_delete=models.SET_NULL,
        related_name="+",
        blank=True,
        null=True,
        help_text=_("Desktop (light mode) preview screenshot."),
    )
    preview_image_desktop_dark = models.ForeignKey(
        settings.WAGTAILIMAGES_IMAGE_MODEL,
        on_delete=models.SET_NULL,
        related_name="+",
        blank=True,
        null=True,
        help_text=_("Desktop (dark mode) preview screenshot."),
    )
    preview_image_tablet = models.ForeignKey(
        settings.WAGTAILIMAGES_IMAGE_MODEL,
        on_delete=models.SET_NULL,
        related_name="+",
        blank=True,
        null=True,
        help_text=_("Tablet (light mode) preview screenshot."),
    )
    preview_image_tablet_dark = models.ForeignKey(
        settings.WAGTAILIMAGES_IMAGE_MODEL,
        on_delete=models.SET_NULL,
        related_name="+",
        blank=True,
        null=True,
        help_text=_("Tablet (dark mode) preview screenshot."),
    )
    preview_image_mobile = models.ForeignKey(
        settings.WAGTAILIMAGES_IMAGE_MODEL,
        on_delete=models.SET_NULL,
        related_name="+",
        blank=True,
        null=True,
        help_text=_("Mobile (light mode) preview screenshot."),
    )
    preview_image_mobile_dark = models.ForeignKey(
        settings.WAGTAILIMAGES_IMAGE_MODEL,
        on_delete=models.SET_NULL,
        related_name="+",
        blank=True,
        null=True,
        help_text=_("Mobile (dark mode) preview screenshot."),
    )

    search_fields = [
        index.FilterField("id"),
        index.AutocompleteField("name"),
        index.AutocompleteField("identifier"),
        index.SearchField("name"),
        index.SearchField("identifier"),
        index.SearchField("description"),
        index.RelatedFields(
            "block",
            [
                index.SearchField("name"),
                index.AutocompleteField("name"),
            ],
        ),
        index.FilterField("block"),
        index.RelatedFields(
            "collection",
            [
                index.SearchField("name"),
                index.AutocompleteField("name"),
            ],
        ),
        index.FilterField("collection_id"),
    ]

    class Meta:
        verbose_name = _("Variant")
        verbose_name_plural = _("Variants")
        ordering = ["block__name", "collection__name", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["block", "collection", "identifier"],
                name="unique_block_collection_variant_identifier",
            ),
            models.UniqueConstraint(
                fields=["block", "identifier"],
                condition=Q(collection=None),
                name="unique_variant_identifier_per_block_no_collection",
            ),
            models.UniqueConstraint(
                fields=["block"],
                condition=Q(is_default=True),
                name="unique_default_variant_per_block",
            ),
        ]

    def __str__(self):
        return self.name


class SharedBlock(index.Indexed, TimestampMixin, models.Model):
    """
    Site-scoped content for shared blocks.

    When a Block has is_shared=True, its content is filled once here
    (per site+locale) and shared across all pages. In page StreamFields,
    editors only see a variant chooser — the content comes from this model.
    """

    block = models.ForeignKey(
        Block,
        on_delete=models.CASCADE,
        related_name="shared_blocks",
        limit_choices_to={"is_shared": True},
        help_text=_("The shared block this content belongs to."),
    )
    site = models.ForeignKey(
        "wagtailcore.Site",
        on_delete=models.CASCADE,
        related_name="shared_blocks",
    )
    locale = models.ForeignKey(
        "wagtailcore.Locale",
        on_delete=models.CASCADE,
        related_name="shared_blocks",
    )
    content = SharedBlockStreamField

    search_fields = [
        index.FilterField("block"),
        index.FilterField("site"),
        index.FilterField("locale"),
        index.RelatedFields(
            "block",
            [
                index.SearchField("name"),
                index.AutocompleteField("name"),
            ],
        ),
    ]

    class Meta:
        verbose_name = _("Shared Block")
        verbose_name_plural = _("Shared Blocks")
        constraints = [
            models.UniqueConstraint(
                fields=["block", "site", "locale"],
                name="unique_shared_block",
            )
        ]

    def __str__(self):
        return f"{self.block.name} ({self.site} / {self.locale})"

    def clean(self):
        super().clean()
        # Ensure the block FK points to a shared block
        if self.block_id and not self.block.is_shared:
            raise ValidationError({"block": ("Only blocks with 'is_shared' enabled can have shared content.")})
        # Ensure the content block type matches the block FK
        if self.block_id and self.content and len(self.content) > 0:
            # ``content[0].block_type`` materializes the first stream item,
            # which recurses into every nested block inside it. A malformed
            # nested value (e.g. a StreamBlock field given `[null, null]`
            # instead of `[{type, value, id}, ...]`) raises a bare
            # TypeError/KeyError/AttributeError from deep inside Wagtail's
            # block machinery, not a ValidationError — left uncaught, that
            # escapes clean() and surfaces as an unhandled 500 instead of a
            # normal validation error. See the equivalent guard in
            # ``phoxtail.api.content.v1._helpers.replace_body``.
            try:
                content_block_type = self.content[0].block_type
            except (TypeError, KeyError, AttributeError, ValueError) as exc:
                raise ValidationError(
                    {
                        "content": (
                            "Content is malformed and could not be read "
                            f"({exc}). Every stream/list block entry — "
                            "including nested ones inside struct fields — "
                            "must be a {'type': ..., 'value': ..., 'id': "
                            "...} dict; None or other placeholder values "
                            "are not valid block entries."
                        )
                    }
                ) from exc
            if content_block_type != self.block.identifier:
                raise ValidationError(
                    {
                        "content": (
                            f"Content block type "
                            f"'{content_block_type}' does "
                            f"not match the selected block "
                            f"'{self.block.identifier}'."
                        )
                    }
                )
