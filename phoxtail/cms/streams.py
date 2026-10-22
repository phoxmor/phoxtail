"""Shared StreamField definitions for phoxtail CMS page models."""

from django.utils.translation import gettext_lazy as _

from phoxtail.streams.blocks import get_dynamic_blocks
from phoxtail.streams.fields import SchemaStreamField

BodyStreamField = SchemaStreamField(
    get_dynamic_blocks,
    null=True,
    blank=True,
    collapsed=True,
    verbose_name=_("body"),
)
