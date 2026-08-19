from django.db import models
from django.utils.translation import gettext_lazy as _


class StreamsAdminPermission(models.Model):
    """
    ContentType anchor for streams admin permissions. Never instantiated —
    exists only so Django creates Permission rows in auth_permission during
    migrate.
    """

    class Meta:
        default_permissions = ()
        permissions: list[tuple[str, str]] = []
        verbose_name = _("Streams")
        verbose_name_plural = _("Streams")
