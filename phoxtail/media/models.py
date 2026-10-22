from django.db import models
from django.utils.translation import gettext_lazy as _
from wagtail.documents.models import AbstractDocument, Document
from wagtail.images.models import AbstractImage, AbstractRendition, Image
from wagtailmedia.models import AbstractMedia


class PhoxtailImage(AbstractImage):
    admin_form_fields = Image.admin_form_fields

    class Meta:
        verbose_name = _("image")
        verbose_name_plural = _("images")


class PhoxtailImageRendition(AbstractRendition):
    image = models.ForeignKey(
        PhoxtailImage, on_delete=models.CASCADE, related_name="renditions", verbose_name=_("image")
    )

    class Meta:
        verbose_name = _("image rendition")
        verbose_name_plural = _("image renditions")
        unique_together = (("image", "filter_spec", "focal_point_key"),)


class PhoxtailDocument(AbstractDocument):
    description = models.TextField(
        blank=True,
        verbose_name=_("Description"),
    )

    admin_form_fields = Document.admin_form_fields + ("description",)


class PhoxtailMedia(AbstractMedia):
    """Covers both video and audio; the `type` field discriminates between them."""

    description = models.TextField(
        blank=True,
        verbose_name=_("Description"),
    )

    admin_form_fields = AbstractMedia.admin_form_fields + ("description",)
