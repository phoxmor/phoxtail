from django import template

register = template.Library()


@register.simple_tag
def dashboard_icon_path(icon_name):
    return f"phoxtail_core/svgs/{icon_name}.html"
