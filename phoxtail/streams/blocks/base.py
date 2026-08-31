from django.template import Context
from django.utils.safestring import mark_safe
from wagtail import blocks

from phoxtail.streams.cache import get_compiled_template, get_default_variant


class BlockVariantStructBlock(blocks.StructBlock):
    """
    Base StructBlock that supports database-driven block variants.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if "_block_identifier" in self.child_blocks:
            del self.child_blocks["_block_identifier"]
        if "_is_shared" in self.child_blocks:
            del self.child_blocks["_is_shared"]

        if "variant" in self.child_blocks:
            variant_block = self.child_blocks.pop("variant")
            self.child_blocks["variant"] = variant_block

    def render(self, value, context=None):
        html = None
        css = ""
        javascript = ""

        is_shared = getattr(self, "_is_shared", False)
        shared_row = None
        if is_shared:
            # A page that places a site-wide block takes over; the hide
            # toggle lets taking over mean "render nothing at all".
            if value.get("hidden"):
                return ""
            # The site-slot render path resolves the row itself and passes it
            # through; per-page refs resolve it from the request context.
            shared_row = value.get("_shared_row") or self._get_shared_block_row(context)
            if shared_row is None or not shared_row.content or len(shared_row.content) == 0:
                return ""
            render_value = shared_row.content[0].value
        else:
            render_value = value

        # Variant cascade: the page's explicit choice, then the site's
        # (SharedBlock.variant), then the block's global default.
        variant = value.get("variant")
        if not variant and shared_row is not None:
            variant = shared_row.variant

        if variant:
            html = variant.html
            css = variant.css or ""
            javascript = variant.javascript or ""
        elif hasattr(self, "_block_identifier"):
            default_variant = get_default_variant(self._block_identifier)
            if default_variant:
                html = default_variant.html
                css = default_variant.css or ""
                javascript = default_variant.javascript or ""
            else:
                return super().render(value, context)

        if html:
            if context is None:
                new_context = self.get_context(render_value)
            else:
                new_context = self.get_context(render_value, parent_context=dict(context))

            template_context = Context(new_context)

            rendered_html = get_compiled_template(html).render(template_context)

            parts = [rendered_html]
            if css:
                rendered_css = get_compiled_template(css).render(template_context)
                parts.append(f"<style>{rendered_css}</style>")
            if javascript:
                rendered_js = get_compiled_template(javascript).render(template_context)
                parts.append(f"<script>{rendered_js}</script>")

            return mark_safe("\n".join(parts))

        return super().render(value, context)

    def _get_shared_block_row(self, context):
        from phoxtail.streams.cache import get_shared_block

        if not context:
            return None

        request = context.get("request")
        if not request:
            return None

        site = getattr(request, "site", None)
        if not site:
            from wagtail.models import Site

            site = Site.find_for_request(request)

        page = context.get("page")
        if page and hasattr(page, "locale"):
            locale = page.locale
        else:
            from wagtail.models import Locale

            locale = Locale.get_default()

        return get_shared_block(self._block_identifier, site, locale)
