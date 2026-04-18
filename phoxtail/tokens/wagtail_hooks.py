from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from wagtail import hooks

from .admin.viewsets import AccessTokensManagementViewSet
from .permissions import AccessTokensAdminPermission


@hooks.register("register_permissions")
def register_access_tokens_permissions():
    """Expose the custom tokens permissions in the Wagtail Groups UI.

    Without this hook the ``access_tokens_management`` /
    ``create_access_tokens`` / ``revoke_access_tokens`` /
    ``manage_all_tokens`` rows would exist in ``auth_permission`` but
    would not appear as checkboxes when editing a Wagtail group.
    """
    content_type = ContentType.objects.get_for_model(AccessTokensAdminPermission)
    return Permission.objects.filter(content_type=content_type)


@hooks.register("register_admin_viewset")
def register_access_tokens_viewset():
    """Mount the Access Tokens admin at ``/admin/access_tokens_management/``.

    Returned as a single viewset rather than a :class:`ModelViewSetGroup`
    because tokens currently have just one admin surface. If further
    token-related viewsets appear, promote this to a group.
    """
    return AccessTokensManagementViewSet()
