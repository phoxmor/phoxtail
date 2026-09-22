**Breaking:** the internal-link list answers one page at a time: pass `limit` and `offset`
to read on, as on every paged list; `total` counts every match, and the
matching MCP tool takes the same two arguments. A search returns its matches
in label order rather than ranked by relevance. Internal links now report
`created_at` and `updated_at` in the same format as every other phoxtail
endpoint (`2026-08-12T06:10:00.446Z`, millisecond precision) instead of
Python's own (`2026-08-12T06:10:00.446154+00:00`).
