"""A font file's URL says where the outside world reaches it.

Same rule as the media API: a relative storage path joins the configured
origin, never the request's own host. See ``phoxtail.core.utils.public_url``.
"""

from __future__ import annotations

import pytest
from django.core.files.base import ContentFile

from phoxtail.design.api.v1._helpers import font_weight_summary
from phoxtail.design.models import FontFamily, FontWeight


@pytest.mark.django_db
def test_font_file_url_is_built_on_the_configured_origin(settings):
    settings.WAGTAILADMIN_BASE_URL = "https://example.com"
    family = FontFamily.objects.create(name="Inter")
    weight = FontWeight.objects.create(
        family=family, weight=400, style="normal", file=ContentFile(b"wOF2", name="inter.woff2")
    )

    assert font_weight_summary(weight)["file_url"] == f"https://example.com{weight.file.url}"
