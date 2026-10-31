import logging

from django import template
from django.utils.safestring import mark_safe

import phoxtail

logger = logging.getLogger(__name__)

register = template.Library()


@register.simple_tag
def icon(name, **kwargs):
    """Render an SVG icon by name.

    Usage:
        {% icon "close" %}
        {% icon "danger" class="al-icon" %}

    An unknown name renders nothing and logs a warning: variants stored in
    the database may name an icon a later release removed, and the page
    must still render.
    """
    try:
        t = template.loader.get_template(f"phoxtail_core/svgs/{name}.html")
    except template.TemplateDoesNotExist:
        logger.warning("Icon '%s' not found", name)
        return ""
    return mark_safe(t.render(kwargs))


@register.simple_tag
def phoxtail_version():
    """Return the installed phoxtail package version.

    Usage:
        {% phoxtail_version %}
    """
    return phoxtail.__version__
