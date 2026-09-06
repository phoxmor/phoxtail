from urllib.parse import unquote

from django import template

register = template.Library()


@register.simple_tag
def dashboard_icon_path(icon_name):
    return f"phoxtail_core/svgs/{icon_name}.html"


def _same_path(one, other):
    """Whether two paths point at the same place.

    One side is usually percent-encoded and the other is not, so a Greek
    slug compares unequal to itself unless both are decoded.
    """
    if not one or not other:
        return False
    return unquote(one) == unquote(other)


def _entry_link(entry, request):
    """A menu entry reduced to what a template needs to draw it, or None.

    None means draw nothing: a target that has been deleted, or a draft in
    front of someone who could not publish it.
    """
    value = entry.value
    label = value.get("label")
    new_tab = bool(value.get("open_in_new_tab"))
    link = {"label": label, "new_tab": new_tab, "current": False, "unpublished": False}

    if entry.block_type == "page":
        page = value.get("page")
        if page is None:
            return None
        page = page.specific
        if not page.live:
            # A draft is worth showing to the person who could publish it,
            # pointed at the preview rather than at a 404.
            if not (request and request.user.has_perm("wagtailadmin.access_admin")):
                return None
            from django.urls import reverse

            return {
                **link,
                "url": reverse("wagtailadmin_pages:view_draft", args=[page.id]),
                "label": label or page.title,
                "unpublished": True,
            }
        url = page.get_url(request=request)
        if url is None:
            return None
        return {**link, "url": url, "label": label or page.title, "current": _is_current(request, url)}

    if entry.block_type == "internal_link":
        internal = value.get("link")
        if internal is None:
            return None
        return {
            **link,
            "url": internal.url,
            "label": label or internal.label,
            "current": _is_current(request, internal.url),
        }

    if entry.block_type == "external_link":
        url = value.get("url")
        if not url:
            return None
        # Never current: an address elsewhere is never the page being read.
        return {**link, "url": url, "label": label or url}

    return None


def _is_current(request, url):
    return bool(request) and _same_path(request.path, url)


@register.simple_tag(takes_context=True)
def menu_entry(context, entry):
    """The entry as a drawable link, or None where it should not be drawn."""
    return _entry_link(entry, context.get("request"))


@register.simple_tag(takes_context=True)
def menu_holds_current_entry(context, items):
    """Whether a dropdown contains the page currently being read."""
    request = context.get("request")
    return any((link := _entry_link(item, request)) and link["current"] for item in items)
