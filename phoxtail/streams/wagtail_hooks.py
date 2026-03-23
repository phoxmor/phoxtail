from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.utils.translation import gettext_lazy as _
from wagtail import hooks
from wagtail.admin.viewsets.model import ModelViewSetGroup

from .permissions import StreamsAdminPermission
from .views import SharedBlockChooserViewSet
from .viewsets import (
    BlockSystemPromptViewSet,
    BlockVariantViewSet,
    BlockViewSet,
    SharedBlockViewSet,
    StudioViewSet,
    VariantCollectionViewSet,
)


@hooks.register("register_permissions")
def register_streams_permissions():
    content_type = ContentType.objects.get_for_model(StreamsAdminPermission)
    return Permission.objects.filter(content_type=content_type)


@hooks.register("register_admin_viewset")
def register_shared_block_chooser():
    return SharedBlockChooserViewSet("shared_block_chooser")


@hooks.register("register_admin_viewset")
class StreamsViewSetGroup(ModelViewSetGroup):
    menu_label = _("Streams")
    menu_icon = "rainy-light"
    show_in_menu = True
    menu_order = 200
    items = (
        BlockViewSet,
        SharedBlockViewSet,
        BlockVariantViewSet,
        VariantCollectionViewSet,
        BlockSystemPromptViewSet,
        StudioViewSet,
    )
