from urllib.parse import unquote

from django import template
from wagtail.models import Page

register = template.Library()


@register.filter
def decode_url(value):
    """Decode URL-encoded strings."""
    if not isinstance(value, str):
        return value
    return unquote(value)


@register.simple_tag(takes_context=True)
def has_active_child(context, items, request_path):
    """Check if any child page in a dropdown matches the current path."""
    decoded_request_path = decode_url(request_path)
    request = context.get("request")

    for item in items:
        if item.block_type == "page":
            page = item.value.get("page")
            if page and isinstance(page, Page):
                page_url = page.get_url(request=request)
                decoded_page_url = decode_url(page_url)
                if decoded_request_path == decoded_page_url:
                    return True

    return False
