"""``phoxtail_blog_list_authors`` MCP tool.

Wraps ``GET /api/blog/v1/authors/``. Used by an agent to resolve a
human-readable author name to the integer FK expected by
``BlogPostPage.author`` before issuing a scalar PATCH.
"""

from __future__ import annotations

import json

from phoxtail.blog.mcp._http import request
from phoxtail.mcp import mcp_server


@mcp_server.tool(
    name="phoxtail_blog_list_authors",
    description=(
        "List/search BlogAuthor snippets by name or email. Returns a list "
        "of {id, title} entries. The integer `id` is the value to pass as "
        "`author` when PATCHing a BlogPostPage. Contributed by the "
        "phoxtail.blog app — only available in projects where blog is "
        "installed."
    ),
)
def list_authors(search: str | None = None, limit: int = 50) -> str:
    resp = request("GET", "/authors/", params={"search": search, "limit": limit})
    resp.raise_for_status()
    return json.dumps(resp.json(), indent=2)
