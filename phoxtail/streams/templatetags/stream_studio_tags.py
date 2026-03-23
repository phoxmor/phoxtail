"""
Template tags for Stream Studio functionality.
"""

import re

from django import template

register = template.Library()


@register.filter(name="minify")
def minify(value):
    """
    Aggressive whitespace normalization for LLM prompt context.
    """
    if not value:
        return ""

    lines = [line.strip() for line in value.splitlines() if line.strip()]
    result = " ".join(lines)
    result = re.sub(r" {2,}", " ", result)

    return result
