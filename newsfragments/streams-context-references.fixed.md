Asking for a block's context with reference variants
(`POST /api/streams/v1/context/` with `references`, and the
`phoxtail_studio_get_context` MCP tool) no longer fails with a server error.
Each reference's block now comes back complete, with its `id`, `source_app`
and `page_types`.
