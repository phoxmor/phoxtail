from django.db import models
from django.utils.translation import gettext_lazy as _


class BlockSiteSlot(models.TextChoices):
    """Named anchors in ``phoxtail_cms/pages/base.html`` where a site-wide
    block renders automatically on every page of a site.

    Head slots hold invisible markup (scripts, meta) and render without an
    addressable wrapper element; body slots wrap their render so the Studio
    can target it.
    """

    HEAD_START = "head_start", _("Head start")
    HEAD_END = "head_end", _("Head end")
    BODY_START = "body_start", _("Body start")
    BEFORE_CONTENT = "before_content", _("Before content")
    AFTER_CONTENT = "after_content", _("After content")
    BODY_END = "body_end", _("Body end")
