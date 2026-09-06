from .registry import DashboardNavItem, registry

MAX_DOCK_SIDE_ITEMS = 3

DASHBOARD_NAV_ITEM = DashboardNavItem(label="Dashboard", url_name="dashboard:index", icon="dashboard", center=True)


def _dock_layout(mobile_items):
    """Arrange mobile nav items around a permanent center anchor.

    Dashboard is the default anchor; a module can claim the center slot
    instead by registering a nav item with center=True. Everything else is
    split in half around it — rather than dealt out alternately — so the
    dock still reads left-to-right in registration order. The left track
    takes the odd item, which balances it against the "More" button sharing
    the right track. Anything past MAX_DOCK_SIDE_ITEMS spills into the
    "More" sheet.
    """
    items = [DASHBOARD_NAV_ITEM, *mobile_items]
    center = next((item for item in mobile_items if item.center), DASHBOARD_NAV_ITEM)
    rest = [item for item in items if item is not center]

    side_items = rest[:MAX_DOCK_SIDE_ITEMS]
    split = (len(side_items) + 1) // 2
    left, right = side_items[:split], side_items[split:]

    return {
        "center": center,
        "left": left,
        "right": right,
        "overflow": rest[MAX_DOCK_SIDE_ITEMS:],
    }


def dashboard_nav(request):
    mobile_items = registry.get_mobile_nav_items()
    return {
        "dashboard_nav_items": registry.get_nav_items(),
        "dashboard_mobile_nav_items": mobile_items,
        "dashboard_dock": _dock_layout(mobile_items),
    }


def dashboard_menu(request):
    """The menu an editor wrote for this site, in the language being read."""
    from phoxtail.dashboard.menus import menu_for_request

    return {"dashboard_menu": menu_for_request(request)}
