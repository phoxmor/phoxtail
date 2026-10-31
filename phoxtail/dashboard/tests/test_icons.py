from django.template import TemplateDoesNotExist
from django.template.loader import get_template

from phoxtail.dashboard.context_processors import DASHBOARD_NAV_ITEM
from phoxtail.dashboard.registry import registry


def test_every_registered_nav_item_and_widget_names_an_icon_that_exists():
    icons = {DASHBOARD_NAV_ITEM.icon}
    icons |= {item.icon for item in registry.get_nav_items()}
    icons |= {widget.icon for widget in registry.get_widgets() if widget.icon}

    missing = []
    for icon in sorted(icons):
        try:
            get_template(f"phoxtail_core/svgs/{icon}.html")
        except TemplateDoesNotExist:
            missing.append(icon)

    assert missing == []
