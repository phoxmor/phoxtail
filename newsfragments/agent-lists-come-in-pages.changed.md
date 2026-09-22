**Breaking:** the inference-provider and model-artifact lists now answer one
page at a time, as `{"items": [...], "total": N}` instead of
`{"providers": [...], "total": N}` and `{"artifacts": [...], "total": N}`.
Pass `limit` and `offset` to read on, as on every paged list; the matching
MCP tools take the same two arguments. A search on either list returns its
matches in the list's own order rather than ranked by relevance.
