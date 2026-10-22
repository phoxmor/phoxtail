import uuid

from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.utils.translation import pgettext_lazy
from wagtail.admin.admin_url_finder import AdminURLFinder


class UUIDMixin(models.Model):
    id = models.BigAutoField(primary_key=True)
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, verbose_name=_("UUID"))

    def get_short_id(self):
        return str(self.uuid)[:8].upper()

    @property
    def short_id(self):
        return self.get_short_id()

    class Meta:
        abstract = True


class TimestampMixin(models.Model):
    created_at = models.DateTimeField(
        auto_now_add=True,
        null=True,
        verbose_name=pgettext_lazy("timestamp", "created at"),
    )
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("updated at"))

    class Meta:
        abstract = True


class AdminURLMixin:
    @property
    def admin_url(self):
        """
        Dynamically build and return this object's edit URL
        in Wagtail's admin.
        """

        return AdminURLFinder().get_edit_url(self)

    @property
    def django_admin_url(self):
        """
        Dynamically build and return this object's edit URL
        in Django's admin.
        """
        return reverse(
            f"admin:{self._meta.app_label}_{self._meta.model_name}_change",
            args=[self.pk],
        )
