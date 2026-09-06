from django.utils.translation import gettext_lazy as _
from wagtail import hooks
from wagtail.admin.viewsets.model import ModelViewSetGroup

from phoxtail.dashboard.viewsets import MenuViewSet


@hooks.register("register_admin_viewset")
class DashboardViewSetGroup(ModelViewSetGroup):
    """One home in the admin for everything an editor writes for the platform.

    A group rather than a lone menu item because the menu is the first of
    several — what sits at the edges of the dashboard is written here too.
    """

    menu_label = _("Platform")
    menu_icon = "dashboard"
    show_in_menu = True
    menu_order = 410
    items = (MenuViewSet,)
