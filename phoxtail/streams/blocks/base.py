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
        if is_shared:
            render_value = self._get_shared_content(context)
            if render_value is None:
                return ""
        else:
            render_value = value

        variant = value.get("variant")

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
                new_context = self.get_context(
                    render_value, parent_context=dict(context)
                )

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

    def _get_shared_content(self, context):
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

        shared_block = get_shared_block(self._block_identifier, site, locale)
        if shared_block and shared_block.content and len(shared_block.content) > 0:
            return shared_block.content[0].value

        return None
