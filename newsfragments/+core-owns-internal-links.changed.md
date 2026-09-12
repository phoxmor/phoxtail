Internal links moved to `/api/core/v1/internal-links/`, out of
`/api/content/v1/`. `InternalLink` is a core model rather than a Wagtail
entity, so the core app now serves it. **Breaking** for any client calling the
old path; the MCP tools and CLI were updated in the same release, and
`phoxtail_content_list_internal_links` keeps its name.
