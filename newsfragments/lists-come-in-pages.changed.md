**Breaking:** the users and genders lists now answer one page at a time, as
`{"items": [...], "total": N}` instead of `{"users": [...], "total": N}` and
`{"genders": [...], "total": N}`. Pass `limit` (default 50, at most 500; more
is refused with 422) and `offset` to read on; `total` counts every match. The
matching MCP tools take the same two arguments. A search on either list now
returns its matches in the list's own order rather than ranked by relevance.
Apps build their API on `phoxtail.api.pagination.Router`, which pages every
list it serves, and can assert none slipped through with `unpaginated()`.
