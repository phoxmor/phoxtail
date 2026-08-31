from django import template
from django.template.loader import render_to_string
from django.urls import NoReverseMatch, reverse
from django.utils.safestring import mark_safe

register = template.Library()


def render_site_wide_block(block, shared_row, context_dict, request=None, content_type_id=None):
    """Render one site-wide block from its resolved SharedBlock row.

    Body-slot renders are wrapped in an addressable fragment element
    (``data-phoxtail-bar-shared-block-id``) so the Studio can refresh and
    target them; head slots hold invisible markup and render bare.
    """
    from phoxtail.streams.cache import get_default_variant, get_dynamic_block_instance
    from phoxtail.streams.constants import BlockSiteSlot

    ref_block = get_dynamic_block_instance(block.identifier, content_type_id=content_type_id)
    if ref_block is None:
        return ""

    inner = ref_block.render({"_shared_row": shared_row}, context_dict)
    if not inner:
        return ""

    if block.site_slot in (BlockSiteSlot.HEAD_START, BlockSiteSlot.HEAD_END):
        return inner

    try:
        fragment_url = reverse(
            "phoxtail_agent:render_shared_block_fragment",
            kwargs={"shared_block_id": shared_row.pk},
        )
    except NoReverseMatch:
        fragment_url = ""

    return render_to_string(
        "phoxtail_cms/partials/shared_block_fragment.html",
        {
            "shared_block": shared_row,
            "block_identifier": block.identifier,
            "slot": block.site_slot,
            "variant": shared_row.variant or get_default_variant(block.identifier),
            "fragment_url": fragment_url,
            "rendered": inner,
        },
        request=request,
    )


@register.simple_tag(takes_context=True)
def block_site_slot(context, slot):
    """Render every site-wide block pinned to the given slot.

    The site provides the block by default; a page whose body places the
    block itself takes over — the automatic render skips that page. A block
    with page-type restrictions renders only on pages of those types.
    """
    from wagtail.models import Locale, Site

    from phoxtail.streams.cache import get_blocks_for_site_slot, get_shared_block

    pinned = get_blocks_for_site_slot(slot)
    if not pinned:
        return ""

    request = context.get("request")
    page = context.get("page")

    site = getattr(request, "site", None)
    if not site and request:
        site = Site.find_for_request(request)
    locale = page.locale if page is not None and hasattr(page, "locale") else Locale.get_default()

    # Top-level block types in the page body — a page carrying its own copy
    # of a site-wide block overrides the automatic render.
    body = getattr(page, "body", None)
    overridden = {child.block_type for child in body} if body else set()

    suppress_untracked = bool(getattr(request, "in_preview_panel", False)) or bool(
        context.get("phoxtail_screenshot_mode")
    )

    page_content_type_id = getattr(page, "content_type_id", None)

    context_dict = context.flatten()
    parts = []
    for block in pinned:
        if block.identifier in overridden:
            continue
        if suppress_untracked and not block.render_in_preview:
            continue
        allowed_types = block.page_types.all()
        if allowed_types and page_content_type_id not in {ct.pk for ct in allowed_types}:
            continue
        shared_row = get_shared_block(block.identifier, site, locale)
        if shared_row is None:
            continue
        rendered = render_site_wide_block(
            block, shared_row, context_dict, request=request, content_type_id=page_content_type_id
        )
        if rendered:
            parts.append(rendered)
    return mark_safe("".join(parts))
