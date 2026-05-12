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
    items = (
        FontFamilyViewSet,
        FontWeightViewSet,
        FontRoleViewSet,
        PaletteSetViewSet,
        PaletteViewSet,
        PaletteRoleViewSet,
    )
