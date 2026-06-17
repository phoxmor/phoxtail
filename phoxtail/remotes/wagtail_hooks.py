from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from wagtail import hooks

from .admin.remotes.viewsets import RemotesViewSet
from .permissions import RemotesAdminPermission


@hooks.register("register_permissions")
def register_remotes_permissions():
    content_type = ContentType.objects.get_for_model(RemotesAdminPermission)
    return Permission.objects.filter(content_type=content_type)


@hooks.register("register_admin_viewset")
def register_remotes_viewset():
    return RemotesViewSet()
