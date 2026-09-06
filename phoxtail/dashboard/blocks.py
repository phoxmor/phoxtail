from django.utils.translation import gettext_lazy as _
from wagtail import blocks
from wagtail.snippets.blocks import SnippetChooserBlock


class MenuEntryBlock(blocks.StructBlock):
    """Common ground for every entry: what it says, and where it opens."""

    label = blocks.CharBlock(
        required=False,
        help_text=_("Entry text. Falls back to the target's own name when empty."),
    )
    open_in_new_tab = blocks.BooleanBlock(
        required=False,
        default=False,
        label=_("Open in new tab"),
    )


class PageLinkBlock(MenuEntryBlock):
    """A page in the site's tree.

    Always offered, even on a platform-only install with no page tree behind
    it: a menu that changes shape with the apps installed could not be moved
    between projects, and an entry type nobody picks costs nothing.
    """

    page = blocks.PageChooserBlock(required=True, help_text=_("The page this entry opens."))

    class Meta:
        icon = "doc-empty"
        label = _("Page")


class InternalLinkBlock(MenuEntryBlock):
    """A named Django route — the way to reach the platform's own screens."""

    link = SnippetChooserBlock(
        "phoxtail_core.InternalLink",
        required=True,
        help_text=_("The route this entry opens."),
    )

    class Meta:
        icon = "link"
        label = _("Internal link")


class ExternalLinkBlock(MenuEntryBlock):
    """Anywhere else — another product, a help centre, a social account."""

    url = blocks.URLBlock(required=True, help_text=_("The address this entry opens."))

    class Meta:
        icon = "site"
        label = _("External link")


class SeparatorBlock(blocks.StructBlock):
    """A break between entries, optionally naming the run that follows it."""

    label = blocks.CharBlock(required=False, help_text=_("Optional heading for the entries below."))

    class Meta:
        icon = "minus"
        label = _("Separator")


class DropdownBlock(blocks.StructBlock):
    """A named group of entries.

    Its items exclude dropdowns: menus that nest without limit are a chore to
    author and impossible to render consistently, and one level has been
    enough everywhere this vocabulary is already in use.
    """

    label = blocks.CharBlock(required=True, help_text=_("Name of the group."))
    items = blocks.StreamBlock(
        [
            ("page", PageLinkBlock()),
            ("internal_link", InternalLinkBlock()),
            ("external_link", ExternalLinkBlock()),
            ("separator", SeparatorBlock()),
        ],
        required=False,
    )

    class Meta:
        icon = "list-ul"
        label = _("Dropdown")


class MenuStreamBlock(blocks.StreamBlock):
    """The entries of one menu, in the order they are shown."""

    page = PageLinkBlock()
    internal_link = InternalLinkBlock()
    external_link = ExternalLinkBlock()
    dropdown = DropdownBlock()
    separator = SeparatorBlock()
