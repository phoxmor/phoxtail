"""Shared StreamField definitions for phoxtail CMS page models."""

from phoxtail.streams.blocks import get_dynamic_blocks
from phoxtail.streams.fields import SchemaStreamField

BodyStreamField = SchemaStreamField(
    get_dynamic_blocks,
    null=True,
    blank=True,
    collapsed=True,
)
