from .registry import registry


def dashboard_nav(request):
    return {
        "dashboard_nav_items": registry.get_nav_items(),
        "dashboard_mobile_nav_items": registry.get_mobile_nav_items(),
    }
