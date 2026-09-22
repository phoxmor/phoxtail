"""How every list tool takes and describes a page.

``Limit`` and ``Offset`` carry the API's bounds into each tool's input
schema, so an agent reads them before it calls rather than learning them
from a refusal.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import Field

from phoxtail.api.pagination import DEFAULT_LIMIT, MAX_LIMIT

Limit = Annotated[int, Field(ge=1, le=MAX_LIMIT, description="Rows to return.")]
Offset = Annotated[int, Field(ge=0, description="Rows to skip.")]

PAGED = (
    "Returns one page: `items`, and `total` counting every match across pages. "
    f"Read on with `offset`; `limit` is {DEFAULT_LIMIT} unless given, at most {MAX_LIMIT}. "
    "When `total` is large, narrow with a filter rather than reading every page."
)
