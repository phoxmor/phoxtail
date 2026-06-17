from django.db import models
from django.utils.translation import gettext_lazy as _


class RemotesAdminPermission(models.Model):
    """
    ContentType anchor for remotes admin permissions. Never instantiated —
    exists only so Django creates Permission rows in auth_permission during
    migrate.
    """

    class Meta:
        default_permissions = ()
        permissions = [("manage_remotes", "Can manage remotes")]
        verbose_name = _("Remotes")
        verbose_name_plural = _("Remotes")
