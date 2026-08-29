from django.utils.translation import gettext_lazy as _
from wagtail import hooks
from wagtail.admin.viewsets.model import ModelViewSetGroup

from .viewsets import (
    FontFamilyViewSet,
    FontRoleViewSet,
    FontWeightViewSet,
    PaletteRoleViewSet,
    PaletteSetViewSet,
    PaletteViewSet,
)


@hooks.register("register_admin_viewset")
class DesignViewSetGroup(ModelViewSetGroup):
    menu_label = _("Design")
    menu_icon = "layers"
    show_in_menu = True
    menu_order = 250
    # Wagtail 8 orders group members by menu_order, so this tuple is no longer
    # what decides the menu. Kept in display order to match what it looks like.
    items = (
        FontFamilyViewSet,
        FontWeightViewSet,
        FontRoleViewSet,
        PaletteSetViewSet,
        PaletteViewSet,
        PaletteRoleViewSet,
    )
