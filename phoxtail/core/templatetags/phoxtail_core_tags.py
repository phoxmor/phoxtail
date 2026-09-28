from django import template
from django.conf import settings

from phoxtail.core.fields import render_control, render_field

register = template.Library()


@register.simple_tag
def field(name, bound_field, **options):
    """Draw a bound form field with one of core's field templates.

    The field sees only what is passed here, never the page's values, so a
    value set higher up cannot change it.

    Usage:
        {% field "input" form.email %}
        {% field "select" form.status show_label=False hx_get=url %}
    """
    return render_field(name, bound_field, **options)


@register.simple_tag
def widget(bound_field, **options):
    """Draw a field's control with Django's own widget, inside a field template.

    Usage:
        {% widget field class="fw-md3-control" placeholder=" " htmx=htmx %}
    """
    return render_control(bound_field, **options)


@register.simple_tag
def get_proper_page_range(paginator, current_page, show_adjacent=1):
    """
    Returns a list of page numbers to display, including:
    - First page
    - Last page
    - Current page
    - show_adjacent pages before and after current page
    - Ellipsis where needed
    """
    total_pages = paginator.num_pages
    page_range = []

    # Always include first page
    page_range.append(1)

    # Calculate range of pages around current page
    start = max(2, current_page - show_adjacent)
    end = min(total_pages - 1, current_page + show_adjacent)

    # Add ellipsis after first page if needed
    if start > 2:
        page_range.append("...")

    # Add pages around current page
    page_range.extend(range(start, end + 1))

    # Add ellipsis before last page if needed
    if end < total_pages - 1:
        page_range.append("...")

    # Always include last page if it's not already included
    if total_pages > 1:
        page_range.append(total_pages)

    return page_range


@register.simple_tag
def app_installed(dotted_name):
    """Return True if the given app is in INSTALLED_APPS.

    Example:
        {% app_installed 'phoxtail.dashboard' as is_dashboard_enabled %}
        {% if is_dashboard_enabled %}...{% endif %}
    """
    from django.apps import apps

    return apps.is_installed(dotted_name)


@register.simple_tag
def setting_enabled(name):
    """Return True if the named setting is truthy.

    Example:
        {% setting_enabled 'PHOXTAIL_ALLOW_SIGNUP' as signup_allowed %}
    """
    return bool(getattr(settings, name, False))
