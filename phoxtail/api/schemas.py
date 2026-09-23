"""Field types every app's API schemas share."""

from __future__ import annotations

from typing import Annotated

from ninja import Field

# Text the model requires: a blank value is refused by the schema, as 422
# naming the field, before the model's own validation can refuse it as an
# opaque 400 — and the API document shows the field as required.
NonBlank = Annotated[str, Field(min_length=1)]
