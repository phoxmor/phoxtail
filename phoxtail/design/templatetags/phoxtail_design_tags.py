from django import template
from django.utils.safestring import mark_safe

import phoxtail

register = template.Library()


@register.simple_tag
def icon(name, **kwargs):
    """Render an SVG icon by name.

    Usage:
        {% icon "close" %}
        {% icon "danger" class="al-icon" %}
    """
    t = template.loader.get_template(f"phoxtail_core/svgs/{name}.html")
    return mark_safe(t.render(kwargs))


@register.simple_tag
def phoxtail_version():
    """Return the installed phoxtail package version.

    Usage:
        {% phoxtail_version %}
    """
    return phoxtail.__version__
